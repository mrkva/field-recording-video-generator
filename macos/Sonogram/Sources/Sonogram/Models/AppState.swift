import Foundation
import SwiftUI
import Combine

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
class AppState: ObservableObject {
    // Audio file
    @Published var audioFile: AudioFileInfo?
    @Published var audioFilePath: String = ""

    // Metadata
    @Published var subject: String = ""
    @Published var location: String = ""
    @Published var coordinates: String = ""
    @Published var recorder: String = ""
    @Published var datetime: String = ""
    @Published var showTimecode: Bool = true

    // Spectrogram settings
    @Published var specMethod: String = "standard"
    @Published var fftWindow: Int = 2048
    @Published var freqMin: Int = 20
    @Published var freqMax: Int = 22050
    @Published var dynamicRange: Int = 55
    @Published var specPPS: Int = 200

    // Output settings
    @Published var selectedFormat: VideoFormat = VideoFormat.all[0]
    @Published var playbackSpeed: String = "1x"
    @Published var normalizeAudio: Bool = true
    @Published var photoPath: String = ""
    @Published var outputPath: String = ""

    // Coordinate picker
    @Published var showCoordinatePicker: Bool = false

    // Error display
    @Published var errorMessage: String?

    // Generation state
    @Published var phase: GenerationPhase = .idle
    @Published var progressLog: [String] = []
    @Published var isGenerating: Bool = false
    @Published var generatedVideoPath: String?

    // Presets & autocomplete
    let presetStore = PresetStore()
    let autocomplete = AutocompleteStore()

    // Save preset sheet
    @Published var showSavePreset: Bool = false

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
        let speed = parseSpeed(playbackSpeed)
        guard speed > 0 else { return nil }
        return file.duration / speed
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
            if let enc = info.encodedBy, !enc.isEmpty {
                recorder = enc
            }
            if let ct = info.creationTime, !ct.isEmpty {
                datetime = ct
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
