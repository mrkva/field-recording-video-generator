import SwiftUI

struct FormatPickerView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        GroupBox("Format") {
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10),
            ], spacing: 10) {
                ForEach(VideoFormat.all) { format in
                    FormatCard(format: format, isSelected: state.selectedFormat.id == format.id)
                        .onTapGesture {
                            withAnimation(.easeInOut(duration: 0.15)) {
                                state.selectedFormat = format
                            }
                        }
                }
            }
            .padding(4)
        }
    }
}

struct FormatCard: View {
    let format: VideoFormat
    let isSelected: Bool

    var body: some View {
        VStack(spacing: 6) {
            aspectPreview
                .frame(height: 50)
                .frame(maxWidth: .infinity)

            Text(format.name)
                .font(.caption)
                .fontWeight(.medium)
                .lineLimit(1)

            Text(format.dimensionLabel)
                .font(.caption2)
                .foregroundStyle(.secondary)

            Text(format.aspectLabel)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(8)
        .background(isSelected ? Color.accentColor.opacity(0.12) : Color.primary.opacity(0.03))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isSelected ? Color.accentColor : Color.clear, lineWidth: 2)
        )
    }

    private var aspectPreview: some View {
        GeometryReader { geo in
            let maxW = geo.size.width - 8
            let maxH = geo.size.height - 4
            let scale = min(maxW / CGFloat(format.width), maxH / CGFloat(format.height))
            let w = CGFloat(format.width) * scale
            let h = CGFloat(format.height) * scale

            RoundedRectangle(cornerRadius: 2)
                .fill(isSelected ? Color.accentColor.opacity(0.3) : Color.secondary.opacity(0.2))
                .frame(width: w, height: h)
                .overlay(
                    RoundedRectangle(cornerRadius: 2)
                        .stroke(Color.secondary.opacity(0.4), lineWidth: 0.5)
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}
