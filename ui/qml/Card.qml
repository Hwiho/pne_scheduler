import QtQuick
import QtQuick.Layouts

// A plain panel: the one surface every page groups content on.
//
// The column is positioned, not anchor-filled: anchoring it to the card while
// deriving the card's implicitHeight from the column's implicitHeight makes
// height depend on itself, which Qt resolves by recursing until the stack ends.
Rectangle {
    id: card
    property string title: ""
    property real padding: Theme.pad
    // Marks the panel a reader should land on first. Carried by border and
    // ground, not colour alone, so it survives a monochrome screenshot.
    property bool accent: false
    default property alias content: inner.data

    color: card.accent ? Theme.accentSoft : Theme.panel
    radius: Theme.radius
    border.color: card.accent ? Theme.accent : Theme.line
    border.width: card.accent ? 2 : 1
    implicitWidth: column.implicitWidth + padding * 2
    implicitHeight: column.implicitHeight + padding * 2

    ColumnLayout {
        id: column
        x: card.padding
        y: card.padding
        width: card.width - card.padding * 2
        spacing: 8

        Text {
            visible: card.title.length > 0
            text: card.title
            color: Theme.accent
            font.pixelSize: 14
            font.bold: true
            Layout.fillWidth: true
        }

        ColumnLayout {
            id: inner
            Layout.fillWidth: true
            spacing: 8
        }
    }
}
