import Foundation

enum CLIEvent {
    case log(String)
    case finished(String)
    case failed(String)
}

struct ProbeError: Error {
    let message: String
}

struct CLIBridge {
    private static let extraPaths = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/opt/local/bin",
    ]

    private static var enrichedPATH: String {
        let current = ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin"
        let missing = extraPaths.filter { !current.contains($0) }
        if missing.isEmpty { return current }
        return (missing + [current]).joined(separator: ":")
    }

    private static func findExecutable(_ name: String) -> String? {
        let searchPaths = extraPaths + ["/usr/bin", "/usr/local/bin"]
        for dir in searchPaths {
            let path = "\(dir)/\(name)"
            if FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        }
        return nil
    }

    static func findSonogramScript() -> String? {
        let candidates = [
            Bundle.main.bundlePath + "/../../../sonogram",
            FileManager.default.currentDirectoryPath + "/sonogram",
            "/usr/local/bin/sonogram",
        ]
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

    /// Read the iXML RIFF chunk from a WAV file. Returns the chunk contents
    /// decoded as UTF-8, with trailing NUL padding and any UTF-8 BOM stripped.
    /// Reads the file header-only via FileHandle so large WAVs aren't loaded
    /// into memory.
    static func readIXML(path: String) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: URL(fileURLWithPath: path)) else {
            return nil
        }
        defer { try? handle.close() }

        guard let header = try? handle.read(upToCount: 12), header.count == 12,
              String(data: header[0..<4], encoding: .ascii) == "RIFF",
              String(data: header[8..<12], encoding: .ascii) == "WAVE"
        else { return nil }

        // Cap how far we'll walk — iXML normally appears before audio data,
        // but RIFF allows any order. 16 MiB is more than enough.
        let scanCap: UInt64 = 16 * 1024 * 1024
        var scanned: UInt64 = 0

        while scanned < scanCap {
            guard let hdr = try? handle.read(upToCount: 8), hdr.count == 8 else { return nil }
            let id = String(data: hdr[0..<4], encoding: .ascii) ?? ""
            let size = hdr[4..<8].withUnsafeBytes { raw -> UInt32 in
                var value: UInt32 = 0
                _ = withUnsafeMutableBytes(of: &value) { dst in
                    raw.copyBytes(to: dst, count: 4)
                }
                return UInt32(littleEndian: value)
            }
            scanned += 8

            if id == "iXML" {
                guard let payload = try? handle.read(upToCount: Int(size)) else { return nil }
                let stripped = payload.prefix(while: { $0 != 0 })
                var text = String(data: stripped, encoding: .utf8) ?? ""
                if text.hasPrefix("\u{feff}") { text.removeFirst() }
                return text.isEmpty ? nil : text
            }

            // Skip chunk body, pad to even boundary.
            let skip = UInt64(size) + UInt64(size % 2)
            do {
                try handle.seek(toOffset: handle.offsetInFile + skip)
            } catch {
                return nil
            }
            scanned += skip
        }
        return nil
    }

    /// Find a first-match value for a tag in an iXML document. iXML is small
    /// and well-defined, so regex is fine and lets us look both at top-level
    /// `<KEY>` and nested `<LOCATION><KEY>` paths.
    static func iXMLValue(_ xml: String, key: String) -> String? {
        let pattern = "<\(key)[^>]*>(.*?)</\(key)>"
        guard let regex = try? NSRegularExpression(
            pattern: pattern,
            options: [.caseInsensitive, .dotMatchesLineSeparators]
        ) else { return nil }
        let range = NSRange(xml.startIndex..., in: xml)
        guard let match = regex.firstMatch(in: xml, range: range),
              match.numberOfRanges > 1,
              let inner = Range(match.range(at: 1), in: xml)
        else { return nil }
        let value = String(xml[inner]).trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }

    static func probeAudio(path: String) async -> Result<AudioFileInfo, ProbeError> {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                guard let ffprobe = findExecutable("ffprobe") else {
                    continuation.resume(returning: .failure(ProbeError(message: "ffprobe not found. Install ffmpeg (brew install ffmpeg).")))
                    return
                }

                let process = Process()
                process.executableURL = URL(fileURLWithPath: ffprobe)
                process.arguments = ["-v", "quiet", "-print_format", "json",
                                    "-show_format", "-show_streams", path]
                process.environment = ProcessInfo.processInfo.environment.merging(
                    ["PATH": enrichedPATH], uniquingKeysWith: { _, new in new }
                )

                let pipe = Pipe()
                let errPipe = Pipe()
                process.standardOutput = pipe
                process.standardError = errPipe

                do {
                    try process.run()
                    process.waitUntilExit()
                } catch {
                    continuation.resume(returning: .failure(ProbeError(message: "Failed to run ffprobe: \(error.localizedDescription)")))
                    return
                }

                if process.terminationStatus != 0 {
                    let errData = errPipe.fileHandleForReading.readDataToEndOfFile()
                    let errText = String(data: errData, encoding: .utf8) ?? ""
                    continuation.resume(returning: .failure(ProbeError(message: "ffprobe failed (exit \(process.terminationStatus)): \(errText)")))
                    return
                }

                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    continuation.resume(returning: .failure(ProbeError(message: "Failed to parse ffprobe output.")))
                    return
                }

                guard let streams = json["streams"] as? [[String: Any]],
                      let audioStream = streams.first(where: { ($0["codec_type"] as? String) == "audio" }),
                      let format = json["format"] as? [String: Any] else {
                    continuation.resume(returning: .failure(ProbeError(message: "No audio stream found in file.")))
                    return
                }

                let sampleRate = Int(audioStream["sample_rate"] as? String ?? "44100") ?? 44100
                let channels = audioStream["channels"] as? Int ?? 1
                let bitsPerSample = audioStream["bits_per_raw_sample"] as? String ?? audioStream["bits_per_sample"] as? String
                let bitDepth = Int(bitsPerSample ?? "16") ?? 16
                let duration = Double(format["duration"] as? String ?? "0") ?? 0

                let tags = format["tags"] as? [String: String] ?? [:]
                let encodedBy = tags["encoded_by"]
                let timeRef = tags["time_reference"]

                // Compose full BWF datetime: origination_date + (time_reference→time
                // or origination_time or creation_time). time_reference (samples
                // since midnight) is preferred because editors update it when
                // trimming the file, while creation_time often stays stale.
                let origDate = tags["origination_date"] ?? tags["date"]
                let origTime = tags["origination_time"]
                let creationTime = tags["creation_time"]

                var derivedTime: String? = nil
                if let tr = timeRef, let trInt = Int(tr), sampleRate > 0 {
                    let totalSecs = Double(trInt) / Double(sampleRate)
                    let h = Int(totalSecs) / 3600
                    let m = (Int(totalSecs) % 3600) / 60
                    let s = Int(totalSecs) % 60
                    derivedTime = String(format: "%02d:%02d:%02d", h, m, s)
                }

                var fullDateTime: String? = nil
                if let date = origDate, date.count >= 10 {
                    let cleanDate = String(date.prefix(10)).replacingOccurrences(of: ":", with: "-")
                    let timeStr = derivedTime ?? origTime ?? creationTime
                    if let t = timeStr {
                        if t.count >= 8 {
                            fullDateTime = "\(cleanDate)T\(String(t.prefix(8)))"
                        } else if t.count >= 5 {
                            fullDateTime = "\(cleanDate)T\(String(t.prefix(5))):00"
                        } else {
                            fullDateTime = "\(cleanDate)T00:00:00"
                        }
                    } else {
                        fullDateTime = "\(cleanDate)T00:00:00"
                    }
                } else if let ct = creationTime, !ct.isEmpty {
                    fullDateTime = ct
                }

                let hasBWF = fullDateTime != nil || timeRef != nil

                // iXML chunk — extract LOCATION_GPS / LOCATION_NAME / SCENE.
                let ixml = Self.readIXML(path: path)
                let coordinates = ixml.flatMap { Self.iXMLValue($0, key: "LOCATION_GPS") }
                let ixmlLocation = ixml.flatMap { Self.iXMLValue($0, key: "LOCATION_NAME") }
                let ixmlScene = ixml.flatMap { Self.iXMLValue($0, key: "SCENE") }

                let filename = URL(fileURLWithPath: path).lastPathComponent

                continuation.resume(returning: .success(AudioFileInfo(
                    path: path,
                    filename: filename,
                    sampleRate: sampleRate,
                    channels: channels,
                    bitDepth: bitDepth,
                    duration: duration,
                    hasBWF: hasBWF,
                    creationTime: fullDateTime,
                    encodedBy: encodedBy,
                    coordinates: coordinates,
                    iXMLLocation: ixmlLocation,
                    iXMLScene: ixmlScene
                )))
            }
        }
    }

    func run(config: [String: String]) -> AsyncStream<CLIEvent> {
        AsyncStream { continuation in
            Task.detached {
                guard let scriptPath = CLIBridge.findSonogramScript() else {
                    continuation.yield(.failed("sonogram script not found. Make sure the app is inside the sonogram repo directory."))
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
                process.executableURL = URL(fileURLWithPath: "/bin/bash")
                process.arguments = [scriptPath, "--config", configPath.path]
                process.environment = ProcessInfo.processInfo.environment.merging(
                    ["PATH": CLIBridge.enrichedPATH], uniquingKeysWith: { _, new in new }
                )

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
