import SwiftUI
import MapKit

struct CoordinatePickerView: View {
    @Binding var coordinates: String
    @Environment(\.dismiss) private var dismiss

    @State private var searchText: String = ""
    @State private var searchResults: [MKMapItem] = []
    @State private var position: MapCameraPosition = .automatic
    @State private var selectedLat: Double = 51.07
    @State private var selectedLon: Double = 0.03
    @State private var pinPlaced: Bool = false
    @State private var isSearching: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Pick Coordinates")
                    .font(.headline)
                Spacer()
                if pinPlaced {
                    Text(formattedCoords)
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 8)

            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(.secondary)
                TextField("Search for a place...", text: $searchText)
                    .textFieldStyle(.plain)
                    .onSubmit { search() }
                if isSearching {
                    ProgressView()
                        .scaleEffect(0.6)
                }
                if !searchText.isEmpty {
                    Button {
                        searchText = ""
                        searchResults = []
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(8)
            .background(.bar)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .padding(.horizontal, 16)

            if !searchResults.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(searchResults, id: \.self) { item in
                            Button {
                                selectResult(item)
                            } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.name ?? "Unknown")
                                        .font(.callout)
                                    if let addr = item.placemark.title {
                                        Text(addr)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(1)
                                    }
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            Divider().padding(.leading, 12)
                        }
                    }
                }
                .frame(maxHeight: 150)
                .background(.regularMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .padding(.horizontal, 16)
                .padding(.top, 4)
            }

            Map(position: $position, interactionModes: [.pan, .zoom]) {
                if pinPlaced {
                    Marker("", coordinate: CLLocationCoordinate2D(latitude: selectedLat, longitude: selectedLon))
                        .tint(.red)
                }
            }
            .mapStyle(.standard(elevation: .flat))
            .onTapGesture { location in
                // MapKit tap gesture doesn't give us coordinates directly in SwiftUI Map,
                // so we use the MapReader approach below
            }
            .overlay(alignment: .center) {
                if !pinPlaced {
                    Image(systemName: "plus")
                        .font(.title3)
                        .foregroundStyle(.secondary.opacity(0.6))
                }
            }
            .overlay(alignment: .bottomTrailing) {
                VStack(spacing: 8) {
                    Button {
                        placeAtCenter()
                    } label: {
                        Label("Pin Center", systemImage: "mappin.and.ellipse")
                            .font(.caption)
                    }
                    .buttonStyle(.bordered)
                    .background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .padding(12)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .padding(.horizontal, 16)
            .padding(.top, 8)

            HStack {
                HStack(spacing: 4) {
                    Text("Lat")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField("51.07", value: $selectedLat, format: .number.precision(.fractionLength(2...6)))
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 100)
                    Text("Lon")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField("0.03", value: $selectedLon, format: .number.precision(.fractionLength(2...6)))
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 100)
                    Button("Go") {
                        pinPlaced = true
                        position = .camera(MapCamera(centerCoordinate: CLLocationCoordinate2D(latitude: selectedLat, longitude: selectedLon), distance: 5000))
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }

                Spacer()

                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button("Use Coordinates") {
                    coordinates = formattedCoords
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!pinPlaced)
                .keyboardShortcut(.defaultAction)
            }
            .padding(16)
        }
        .frame(width: 600, height: 500)
        .onAppear {
            parseExisting()
        }
    }

    private var formattedCoords: String {
        String(format: "%.4f, %.4f", selectedLat, selectedLon)
    }

    private func parseExisting() {
        let parts = coordinates.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        if parts.count == 2, let lat = Double(parts[0]), let lon = Double(parts[1]) {
            selectedLat = lat
            selectedLon = lon
            pinPlaced = true
            position = .camera(MapCamera(centerCoordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon), distance: 50000))
        } else {
            position = .camera(MapCamera(centerCoordinate: CLLocationCoordinate2D(latitude: 30, longitude: 0), distance: 20000000))
        }
    }

    private func search() {
        guard !searchText.isEmpty else { return }
        isSearching = true
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = searchText
        let search = MKLocalSearch(request: request)
        search.start { response, _ in
            isSearching = false
            searchResults = response?.mapItems ?? []
        }
    }

    private func selectResult(_ item: MKMapItem) {
        let coord = item.placemark.coordinate
        selectedLat = coord.latitude
        selectedLon = coord.longitude
        pinPlaced = true
        searchResults = []
        searchText = item.name ?? ""
        position = .camera(MapCamera(centerCoordinate: coord, distance: 5000))
    }

    private func placeAtCenter() {
        pinPlaced = true
    }
}
