import Foundation
import SwiftUI

struct VideoFormat: Identifiable, Hashable {
    let id: String
    let name: String
    let width: Int
    let height: Int
    let fps: Int
    let description: String
    let icon: String

    var aspectLabel: String {
        let g = gcd(width, height)
        return "\(width/g):\(height/g)"
    }

    var dimensionLabel: String {
        "\(width)×\(height)"
    }

    var isVertical: Bool { height > width }
    var isSquare: Bool { width == height }

    private func gcd(_ a: Int, _ b: Int) -> Int {
        b == 0 ? a : gcd(b, a % b)
    }

    static let all: [VideoFormat] = [
        VideoFormat(id: "ig_reel", name: "IG Reel", width: 1080, height: 1920, fps: 60,
                    description: "Instagram-safe vertical with safe zones",
                    icon: "iphone"),
        VideoFormat(id: "reel", name: "Reel", width: 1080, height: 1920, fps: 60,
                    description: "Full-bleed vertical video",
                    icon: "rectangle.portrait"),
        VideoFormat(id: "square", name: "Square", width: 1080, height: 1080, fps: 60,
                    description: "Square format for feeds",
                    icon: "square"),
        VideoFormat(id: "landscape", name: "Landscape", width: 1920, height: 1080, fps: 60,
                    description: "Standard 16:9 horizontal",
                    icon: "rectangle"),
        VideoFormat(id: "cf-u1", name: "CF-U1 Kiosk", width: 1024, height: 600, fps: 30,
                    description: "Panasonic CF-U1, baseline H.264",
                    icon: "desktopcomputer"),
        VideoFormat(id: "cf-33", name: "CF-33 Kiosk", width: 2160, height: 1440, fps: 30,
                    description: "Panasonic CF-33, 3:2 display",
                    icon: "laptopcomputer"),
    ]

    static func find(_ id: String) -> VideoFormat? {
        all.first { $0.id == id }
    }
}

struct UserPreset: Identifiable, Codable, Hashable {
    let id: UUID
    var name: String
    var formatID: String
    var specMethod: String
    var fftWindow: Int
    var freqMin: Int
    var freqMax: Int
    var dynamicRange: Int
    var specPPS: Int
    var colormap: String
    var playbackSpeed: String
    var normalizeAudio: Bool
    var showTimecode: Bool
    var subject: String
    var location: String
    var coordinates: String
    var recorder: String

    @MainActor init(name: String, from state: AppState) {
        self.id = UUID()
        self.name = name
        self.formatID = state.selectedFormat.id
        self.specMethod = state.specMethod
        self.fftWindow = state.fftWindow
        self.freqMin = state.freqMin
        self.freqMax = state.freqMax
        self.dynamicRange = state.dynamicRange
        self.specPPS = state.specPPS
        self.colormap = state.colormap
        self.playbackSpeed = state.playbackSpeed
        self.normalizeAudio = state.normalizeAudio
        self.showTimecode = state.showTimecode
        self.subject = state.subject
        self.location = state.location
        self.coordinates = state.coordinates
        self.recorder = state.recorder
    }

    @MainActor func apply(to state: AppState) {
        if let fmt = VideoFormat.find(formatID) {
            state.selectedFormat = fmt
        }
        state.specMethod = specMethod
        state.fftWindow = fftWindow
        state.freqMin = freqMin
        state.freqMax = freqMax
        state.dynamicRange = dynamicRange
        state.specPPS = specPPS
        state.colormap = colormap
        state.playbackSpeed = playbackSpeed
        state.normalizeAudio = normalizeAudio
        state.showTimecode = showTimecode
        state.subject = subject
        state.location = location
        state.coordinates = coordinates
        state.recorder = recorder
    }
}

@MainActor
class PresetStore: ObservableObject {
    @Published var presets: [UserPreset] = []

    private let storePath: URL

    init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("Sonogram", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        storePath = dir.appendingPathComponent("presets.json")
        load()
    }

    func save(preset: UserPreset) {
        if let idx = presets.firstIndex(where: { $0.id == preset.id }) {
            presets[idx] = preset
        } else {
            presets.append(preset)
        }
        persist()
    }

    func delete(preset: UserPreset) {
        presets.removeAll { $0.id == preset.id }
        persist()
    }

    private func load() {
        guard let data = try? Data(contentsOf: storePath),
              let decoded = try? JSONDecoder().decode([UserPreset].self, from: data) else {
            return
        }
        presets = decoded
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(presets) {
            try? data.write(to: storePath)
        }
    }
}
