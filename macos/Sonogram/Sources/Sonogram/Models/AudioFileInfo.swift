import Foundation

struct AudioFileInfo {
    let path: String
    let filename: String
    let sampleRate: Int
    let channels: Int
    let bitDepth: Int
    let duration: Double
    let hasBWF: Bool
    let creationTime: String?
    let encodedBy: String?

    var nyquist: Int { sampleRate / 2 }

    var durationFormatted: String {
        let m = Int(duration) / 60
        let s = Int(duration) % 60
        let ms = Int((duration - Double(Int(duration))) * 100)
        return String(format: "%d:%02d.%02d", m, s, ms)
    }

    var channelLabel: String {
        switch channels {
        case 1: return "Mono"
        case 2: return "Stereo"
        default: return "\(channels)ch"
        }
    }

    var sampleRateLabel: String {
        if sampleRate >= 1000 {
            let khz = Double(sampleRate) / 1000.0
            if khz == Double(Int(khz)) {
                return "\(Int(khz)) kHz"
            }
            return String(format: "%.1f kHz", khz)
        }
        return "\(sampleRate) Hz"
    }

    var bitDepthLabel: String { "\(bitDepth)-bit" }
}
