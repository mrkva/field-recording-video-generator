import Foundation

enum CLIEvent {
    case log(String)
    case finished(String)
    case failed(String)
}

struct CLIBridge {
    static func findSonogramScript() -> String? {
        let candidates = [
            Bundle.main.bundlePath + "/../../../sonogram",
            FileManager.default.currentDirectoryPath + "/sonogram",
            "/usr/local/bin/sonogram",
        ]
        // Also check parent directories of the app bundle
        if let appPath = Bundle.main.bundlePath.components(separatedBy: "/macos/").first {
            let repoScript = appPath + "/sonogram"
            if FileManager.default.isExecutableFile(atPath: repoScript) {
                return repoScript
            }
        }
        for path in candidates {
            if FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        }
        return nil
    }

    static func probeAudio(path: String) async -> AudioFileInfo? {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_format", "-show_streams", path]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }

        guard let streams = json["streams"] as? [[String: Any]],
              let audioStream = streams.first(where: { ($0["codec_type"] as? String) == "audio" }),
              let format = json["format"] as? [String: Any] else {
            return nil
        }

        let sampleRate = Int(audioStream["sample_rate"] as? String ?? "44100") ?? 44100
        let channels = audioStream["channels"] as? Int ?? 1
        let bitsPerSample = audioStream["bits_per_raw_sample"] as? String ?? audioStream["bits_per_sample"] as? String
        let bitDepth = Int(bitsPerSample ?? "16") ?? 16
        let duration = Double(format["duration"] as? String ?? "0") ?? 0

        let tags = format["tags"] as? [String: String] ?? [:]
        let creationTime = tags["creation_time"] ?? tags["date"]
        let encodedBy = tags["encoded_by"]
        let timeRef = tags["time_reference"]
        let hasBWF = creationTime != nil || timeRef != nil

        let filename = URL(fileURLWithPath: path).lastPathComponent

        return AudioFileInfo(
            path: path,
            filename: filename,
            sampleRate: sampleRate,
            channels: channels,
            bitDepth: bitDepth,
            duration: duration,
            hasBWF: hasBWF,
            creationTime: creationTime,
            encodedBy: encodedBy
        )
    }

    func run(config: [String: String]) -> AsyncStream<CLIEvent> {
        AsyncStream { continuation in
            Task.detached {
                guard let scriptPath = CLIBridge.findSonogramScript() else {
                    continuation.yield(.failed("sonogram script not found"))
                    continuation.finish()
                    return
                }

                let tempDir = FileManager.default.temporaryDirectory
                let configPath = tempDir.appendingPathComponent("sonogram_config_\(UUID().uuidString).conf")

                var configText = ""
                for (key, value) in config.sorted(by: { $0.key < $1.key }) {
                    configText += "\(key)=\(value)\n"
                }

                do {
                    try configText.write(to: configPath, atomically: true, encoding: .utf8)
                } catch {
                    continuation.yield(.failed("Failed to write config: \(error)"))
                    continuation.finish()
                    return
                }

                let process = Process()
                process.executableURL = URL(fileURLWithPath: scriptPath)
                process.arguments = ["--config", configPath.path]

                let stdoutPipe = Pipe()
                let stderrPipe = Pipe()
                process.standardOutput = stdoutPipe
                process.standardError = stderrPipe

                let scriptDir = URL(fileURLWithPath: scriptPath).deletingLastPathComponent().path
                process.currentDirectoryURL = URL(fileURLWithPath: scriptDir)

                stdoutPipe.fileHandleForReading.readabilityHandler = { handle in
                    let data = handle.availableData
                    if data.isEmpty { return }
                    if let text = String(data: data, encoding: .utf8) {
                        for line in text.components(separatedBy: .newlines) where !line.isEmpty {
                            let clean = line.replacingOccurrences(
                                of: "\u{1B}\\[[0-9;]*m",
                                with: "",
                                options: .regularExpression
                            )
                            continuation.yield(.log(clean))
                        }
                    }
                }

                stderrPipe.fileHandleForReading.readabilityHandler = { handle in
                    let data = handle.availableData
                    if data.isEmpty { return }
                    if let text = String(data: data, encoding: .utf8) {
                        for line in text.components(separatedBy: .newlines) where !line.isEmpty {
                            let clean = line.replacingOccurrences(
                                of: "\u{1B}\\[[0-9;]*m",
                                with: "",
                                options: .regularExpression
                            )
                            continuation.yield(.log(clean))
                        }
                    }
                }

                do {
                    try process.run()
                    process.waitUntilExit()
                } catch {
                    continuation.yield(.failed("Failed to launch: \(error)"))
                    continuation.finish()
                    return
                }

                stdoutPipe.fileHandleForReading.readabilityHandler = nil
                stderrPipe.fileHandleForReading.readabilityHandler = nil

                try? FileManager.default.removeItem(at: configPath)

                if process.terminationStatus == 0 {
                    let outputFile = config["OUTPUT_FILE"] ?? ""
                    continuation.yield(.finished(outputFile))
                } else {
                    continuation.yield(.failed("Process exited with code \(process.terminationStatus)"))
                }
                continuation.finish()
            }
        }
    }
}
