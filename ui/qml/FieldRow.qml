import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One parameter: label, an editor in its own unit, and the derived reading,
// allowed range, basis, and any issue underneath it.
ColumnLayout {
    id: row
    property var field: ({})
    property int siblingCount: 1
    property string localError: ""

    signal commit(string key, string value)
    signal applyAll(string key, string value)

    spacing: 3
    Layout.fillWidth: true

    function currentValue() {
        if (!editor.item)
            return field.value
        if (field.kind === "bool")
            return editor.item.checked ? "예" : "아니오"
        if (field.kind === "choice")
            return editor.item.currentText
        return editor.item.text
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Text {
            Layout.preferredWidth: 168
            text: field.risk === "critical" ? field.label + " ⚠" : field.label
            color: field.risk === "critical" ? Theme.danger : Theme.ink
            font.pixelSize: 13
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Loader {
            id: editor
            Layout.preferredWidth: 210
            sourceComponent: field.kind === "bool" ? boolEditor
                           : field.kind === "choice" ? choiceEditor : textEditor
        }

        Text {
            text: field.unit
            color: Theme.muted
            font.pixelSize: 11
            visible: field.kind !== "bool" && field.kind !== "choice"
        }

        Item { Layout.fillWidth: true }

        Button {
            visible: row.siblingCount > 1
            text: "같은 실험 " + row.siblingCount + "개에 적용"
            font.pixelSize: 11
            onClicked: row.applyAll(row.field.key, row.currentValue())
        }
    }

    Component {
        id: textEditor
        TextField {
            text: row.field.value
            selectByMouse: true
            color: Theme.ink
            onEditingFinished: if (text !== row.field.value) row.commit(row.field.key, text)
        }
    }

    Component {
        id: choiceEditor
        ComboBox {
            model: row.field.choices
            currentIndex: Math.max(0, row.field.choices.indexOf(row.field.value))
            onActivated: if (currentText !== row.field.value) row.commit(row.field.key, currentText)
        }
    }

    Component {
        id: boolEditor
        CheckBox {
            checked: row.field.checked
            text: checked ? "사용" : "사용 안 함"
            onToggled: row.commit(row.field.key, checked ? "예" : "아니오")
        }
    }

    Text {
        Layout.fillWidth: true
        Layout.leftMargin: 176
        visible: text.length > 0
        text: {
            var parts = []
            if (row.field.detail) parts.push("→ " + row.field.detail)
            if (row.field.help) parts.push(row.field.help)
            if (row.field.range) parts.push(row.field.range)
            if (row.field.basis) parts.push("근거: " + row.field.basis)
            if (row.field.affects) parts.push("영향: " + row.field.affects)
            if (row.field.verification) parts.push("검증: " + row.field.verification)
            return parts.join("\n")
        }
        color: Theme.muted
        font.pixelSize: 11
        wrapMode: Text.WordWrap
        lineHeight: 1.25
    }

    Text {
        Layout.fillWidth: true
        Layout.leftMargin: 176
        visible: text.length > 0
        text: row.localError.length > 0
              ? "오류: " + row.localError
              : (row.field.issues ? row.field.issues.join("\n") : "")
        color: row.localError.length > 0 || row.field.hasError ? Theme.danger : Theme.warn
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }
}
