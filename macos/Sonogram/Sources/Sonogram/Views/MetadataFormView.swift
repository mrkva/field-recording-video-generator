import SwiftUI

struct MetadataFormView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        GroupBox("Metadata") {
            VStack(alignment: .leading, spacing: 10) {
                fieldRow("Subject", text: $state.subject, field: .subject,
                         placeholder: "Dawn chorus at oak woodland edge")
                fieldRow("Location", text: $state.location, field: .location,
                         placeholder: "Ashdown Forest, East Sussex, UK")
                fieldRow("Coordinates", text: $state.coordinates, field: .coordinates,
                         placeholder: "51.07, 0.03")
                fieldRow("Recorder", text: $state.recorder, field: .recorder,
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

    private func fieldRow(_ label: String, text: Binding<String>, field: AutocompleteStore.Field, placeholder: String) -> some View {
        HStack {
            Text(label)
                .frame(width: 80, alignment: .trailing)
                .foregroundStyle(.secondary)
            AutocompleteTextField(
                text: text,
                placeholder: placeholder,
                suggestions: { prefix in
                    state.autocomplete.suggestions(for: field, prefix: prefix)
                }
            )
        }
    }
}

struct AutocompleteTextField: View {
    @Binding var text: String
    let placeholder: String
    let suggestions: (String) -> [String]

    @State private var showSuggestions = false
    @State private var currentSuggestions: [String] = []
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            TextField(placeholder, text: $text)
                .textFieldStyle(.roundedBorder)
                .focused($isFocused)
                .onChange(of: text) { _, newValue in
                    currentSuggestions = suggestions(newValue)
                    showSuggestions = isFocused && !currentSuggestions.isEmpty && !currentSuggestions.contains(newValue)
                }
                .onChange(of: isFocused) { _, focused in
                    if focused {
                        currentSuggestions = suggestions(text)
                        showSuggestions = !currentSuggestions.isEmpty && !currentSuggestions.contains(text)
                    } else {
                        // Delay hiding to allow click on suggestion
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                            showSuggestions = false
                        }
                    }
                }

            if showSuggestions {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(currentSuggestions.prefix(5), id: \.self) { suggestion in
                        Button {
                            text = suggestion
                            showSuggestions = false
                        } label: {
                            Text(suggestion)
                                .font(.callout)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Color.primary.opacity(0.05))
                    }
                }
                .background(.regularMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .shadow(radius: 4)
            }
        }
    }
}
