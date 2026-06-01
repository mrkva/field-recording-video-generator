import Foundation
import SwiftUI
import Observation

enum GenerationPhase: String {
    case idle = "Ready"
    case probing = "Probing audio..."
    case spectrogram = "Rendering spectrogram..."
    case infoPanel = "Rendering info panel..."
    case freqScale = "Rendering frequency scale..."
    case mapAnimation = "Rendering map animation..."
    case compositing = "Compositing video..."
    case done = "Done"
    case failed = "Failed"
}

@MainActor
@Observable
class AppState {
    var audioFile: AudioFileInfo?
    var audioFilePath: String = ""

    var subject: String = ""
    var location: String = ""
    var coordinates: String = ""
    var recorder: String = ""
    var datetime: String = ""
    var showTimecode: Bool = true

    var specMethod: String = "standard"
    var fftWindow: Int = 2048
    var freqMin: Int = 20
    var freqMax: Int = 22050
    var dynamicRange: Int = 55
    var specPPS: Int = 200
    var colormap: String = "inferno"

    var selectedFormat: VideoFormat = VideoFormat.all[0]
    var playbackSpeed: String = "1x"
    var normalizeAudio: Bool = true
    var photoPath: String = ""
    var outputPath: String = ""
    var openAfterExport: Bool = false

    var showCoordinatePicker: Bool = false
    var errorMessage: String?

    var phase: GenerationPhase = .idle
    var progressLog: [String] = []
    var isGenerating: Bool = false
    var generatedVideoPath: String?

    let presetStore = PresetStore()
    let autocomplete = AutocompleteStore()
    var showSavePreset: Bool = false

    var fftHint: String {
        if specMethod == "reassigned" {
            return "Reassigned method recovers frequency detail from small windows. 256-512 for birdsong/transients, 1024+ for tonal sounds."
        } else {
            return "Larger = better frequency resolution, worse time resolution. 1024-2048 for birdsong, 4096+ for low-frequency or tonal."
        }
    }

    var defaultFFT: Int {
        specMethod == "reassigned" ? 512 : 2048
    }

    var estimatedDuration: Double? {
        guard let file = audioFile else { return nil }
        let n = parseSpeed(playbackSpeed)
        guard n > 0 else { return nil }
        // Match the bash side's heuristic exactly:
        //   n  < 1: playback-speed multiplier → output = duration / n
        //   n >= 1: slowdown factor           → output = duration × n
        // Both interpretations slow the audio down; entries >= 1 keep the
        // legacy "Nx slower" CLI meaning, while < 1 reads as "Nx speed".
        let slowdown = n < 1 ? 1.0 / n : n
        return file.duration * slowdown
    }

    var estimatedDurationFormatted: String {
        guard let dur = estimatedDuration else { return "—" }
        let m = Int(dur) / 60
        let s = Int(dur) % 60
        return String(format: "%d:%02d", m, s)
    }

    func parseSpeed(_ input: String) -> Double {
        let cleaned = input.lowercased().trimmingCharacters(in: .whitespaces)
        if cleaned.hasSuffix("x"), let val = Double(cleaned.dropLast()) {
            return val
        }
        if let val = Double(cleaned) {
            return val
        }
        return 1.0
    }

    func loadAudioFile(url: URL) async {
        audioFilePath = url.path
        errorMessage = nil

        let result = await CLIBridge.probeAudio(path: url.path)
        switch result {
        case .success(let info):
            audioFile = info
            freqMax = info.nyquist
            if let ct = info.creationTime, !ct.isEmpty {
                datetime = ct
            }
            // Auto-fill from iXML when the user hasn't typed anything yet,
            // so loading a different file doesn't overwrite their input.
            // Equipment prefers iXML's structured AUDIO_RECORDER_MODEL +
            // MICROPHONE_MODEL over BWF's plain encoded_by tag.
            if recorder.isEmpty {
                if let eq = info.iXMLEquipment, !eq.isEmpty {
                    recorder = eq
                } else if let enc = info.encodedBy, !enc.isEmpty {
                    recorder = enc
                }
            }
            if coordinates.isEmpty, let coords = info.coordinates, !coords.isEmpty {
                coordinates = coords
            }
            if location.isEmpty, let loc = info.iXMLLocation, !loc.isEmpty {
                location = loc
            }
            if subject.isEmpty, let scene = info.iXMLScene, !scene.isEmpty {
                subject = scene
            }
            showTimecode = info.hasBWF
        case .failure(let error):
            audioFile = nil
            errorMessage = error.message
        }

        if outputPath.isEmpty {
            let stem = url.deletingPathExtension().lastPathComponent
            let dir = url.deletingLastPathComponent().path
            outputPath = "\(dir)/\(stem)_video.mp4"
        }
    }

    func loadPreset(_ preset: UserPreset) {
        preset.apply(to: self)
    }

    func generate() async {
        guard !audioFilePath.isEmpty else { return }
        isGenerating = true
        phase = .probing
        progressLog = []
        generatedVideoPath = nil

        let config = buildConfig()
        let bridge = CLIBridge()

        for await event in bridge.run(config: config) {
            switch event {
            case .log(let line):
                progressLog.append(line)
                updatePhase(from: line)
            case .finished(let outputPath):
                phase = .done
                generatedVideoPath = outputPath
            case .failed(let error):
                phase = .failed
                progressLog.append("ERROR: \(error)")
            }
        }

        isGenerating = false
    }

    func buildConfig() -> [String: String] {
        var config: [String: String] = [:]
        config["INPUT"] = audioFilePath
        config["DATETIME"] = datetime
        config["SUBJECT"] = subject
        config["RECORDER"] = recorder
        config["LOCATION"] = location
        config["COORDINATES"] = coordinates
        config["FREQ_MIN"] = String(freqMin)
        config["FREQ_MAX"] = String(freqMax)
        config["FFT_WINDOW"] = String(fftWindow)
        config["SPEC_METHOD"] = specMethod
        config["SPEC_PPS"] = String(specPPS)
        config["DYNAMIC_RANGE"] = String(dynamicRange)
        config["COLORMAP"] = colormap
        config["PLAYBACK_SPEED_INPUT"] = playbackSpeed
        config["NORMALIZE_AUDIO"] = normalizeAudio ? "y" : "n"
        config["PRESET"] = selectedFormat.id
        config["PHOTO_PATH"] = photoPath
        config["SHOW_TIMECODE"] = showTimecode ? "y" : "n"
        config["OUTPUT_FILE"] = outputPath
        return config
    }

    private func updatePhase(from line: String) {
        let lower = line.lowercased()
        if lower.contains("spectrogram") && lower.contains("render") {
            phase = .spectrogram
        } else if lower.contains("info panel") || lower.contains("info_panel") {
            phase = .infoPanel
        } else if lower.contains("freq") && lower.contains("scale") {
            phase = .freqScale
        } else if lower.contains("map") && (lower.contains("render") || lower.contains("animat")) {
            phase = .mapAnimation
        } else if lower.contains("ffmpeg") || lower.contains("composit") || lower.contains("encoding") {
            phase = .compositing
        }
    }
}
