import SwiftUI

struct MetadataFormView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        GroupBox("Metadata") {
            VStack(alignment: .leading, spacing: 10) {
                fieldRow("Subject", text: $state.subject,
                         placeholder: "Dawn chorus at oak woodland edge")
                fieldRow("Location", text: $state.location,
                         placeholder: "Ashdown Forest, East Sussex, UK")
                HStack {
                    Text("Coordinates")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    TextField("51.07, 0.03", text: $state.coordinates)
                        .textFieldStyle(.roundedBorder)
                    Button {
                        state.showCoordinatePicker = true
                    } label: {
                        Image(systemName: "map")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .help("Pick from map")
                }
                fieldRow("Equipment", text: $state.recorder,
                         placeholder: "Zoom H5 + Sennheiser MKH 8020")

                HStack {
                    Text("Date/Time")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    TextField("2024-03-15T14:30:22", text: $state.datetime)
                        .textFieldStyle(.roundedBorder)
                    if state.audioFile?.hasBWF == true {
                        Label("BWF", systemImage: "clock.badge.checkmark")
                            .font(.caption2)
                            .foregroundStyle(.green)
                    }
                }
            }
            .padding(4)
        }
    }

    private func fieldRow(_ label: String, text: Binding<String>, placeholder: String) -> some View {
        HStack {
            Text(label)
                .frame(width: 80, alignment: .trailing)
                .foregroundStyle(.secondary)
            TextField(placeholder, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }
}
