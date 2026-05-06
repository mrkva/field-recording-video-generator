import Foundation

struct Preset: Identifiable, Hashable {
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

    static let all: [Preset] = [
        Preset(id: "ig_reel", name: "IG Reel", width: 1080, height: 1920, fps: 60,
               description: "Instagram-safe vertical with safe zones for UI overlays",
               icon: "iphone"),
        Preset(id: "reel", name: "Reel", width: 1080, height: 1920, fps: 60,
               description: "Full-bleed vertical video, no safe zone padding",
               icon: "rectangle.portrait"),
        Preset(id: "square", name: "Square", width: 1080, height: 1080, fps: 60,
               description: "Square format for feeds and thumbnails",
               icon: "square"),
        Preset(id: "landscape", name: "Landscape", width: 1920, height: 1080, fps: 60,
               description: "Standard 16:9 horizontal video",
               icon: "rectangle"),
        Preset(id: "cf-u1", name: "CF-U1 Kiosk", width: 1024, height: 600, fps: 30,
               description: "Panasonic Toughbook CF-U1: baseline H.264, software decode",
               icon: "desktopcomputer"),
        Preset(id: "cf-33", name: "CF-33 Kiosk", width: 2160, height: 1440, fps: 30,
               description: "Panasonic Toughbook CF-33: 3:2 high-res display",
               icon: "laptopcomputer"),
    ]

    static func find(_ id: String) -> Preset? {
        all.first { $0.id == id }
    }
}
