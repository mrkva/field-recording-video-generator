import Foundation

@MainActor
class AutocompleteStore: ObservableObject {
    @Published var subjects: [String] = []
    @Published var locations: [String] = []
    @Published var recorders: [String] = []
    @Published var coordinates: [String] = []

    private let storePath: URL

    init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("Sonogram", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        storePath = dir.appendingPathComponent("autocomplete.json")
        load()
    }

    func addEntry(subject: String, location: String, recorder: String, coords: String) {
        if !subject.isEmpty && !subjects.contains(subject) {
            subjects.insert(subject, at: 0)
            if subjects.count > 100 { subjects.removeLast() }
        }
        if !location.isEmpty && !locations.contains(location) {
            locations.insert(location, at: 0)
            if locations.count > 100 { locations.removeLast() }
        }
        if !recorder.isEmpty && !recorders.contains(recorder) {
            recorders.insert(recorder, at: 0)
            if recorders.count > 50 { recorders.removeLast() }
        }
        if !coords.isEmpty && !coordinates.contains(coords) {
            coordinates.insert(coords, at: 0)
            if coordinates.count > 100 { coordinates.removeLast() }
        }
        save()
    }

    private func load() {
        guard let data = try? Data(contentsOf: storePath),
              let dict = try? JSONSerialization.jsonObject(with: data) as? [String: [String]] else {
            return
        }
        subjects = dict["subjects"] ?? []
        locations = dict["locations"] ?? []
        recorders = dict["recorders"] ?? []
        coordinates = dict["coordinates"] ?? []
    }

    private func save() {
        let dict: [String: [String]] = [
            "subjects": subjects,
            "locations": locations,
            "recorders": recorders,
            "coordinates": coordinates,
        ]
        if let data = try? JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted) {
            try? data.write(to: storePath)
        }
    }
}
