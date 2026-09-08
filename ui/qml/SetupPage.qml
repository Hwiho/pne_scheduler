import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 1. 설정 — which cycler, which cell. Everything downstream depends on this.
ScrollView {
    id: page
    clip: true
    property var rows: []

    function reload() { rows = workspace.setupFields() }

    Connections {
        target: workspace
        function onChanged() { page.reload() }
    }
    Component.onCompleted: reload()

    ColumnLayout {
        width: page.availableWidth
        spacing: 12

        Text {
            text: "이 스케줄이 어떤 장비에서, 어떤 셀로 도는지 먼저 정합니다."
            color: Theme.muted
            font.pixelSize: 12
        }

        Card {
            Layout.fillWidth: true
            title: "장비 · 셀"

            Repeater {
                model: page.rows

                ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 2

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            Layout.preferredWidth: 150
                            text: modelData.label
                            color: Theme.ink
                            font.pixelSize: 13
                            font.bold: true
                        }

                        Loader {
                            id: setupEditor
                            Layout.preferredWidth: 260
                            sourceComponent: modelData.choices.length > 0 ? unitBox
                                           : modelData.readOnly ? readOnlyBox : valueBox

                            Component {
                                id: valueBox
                                TextField {
                                    text: modelData.value
                                    selectByMouse: true
                                    onEditingFinished: {
                                        if (text === modelData.value)
                                            return
                                        var result = workspace.setSetupValue(modelData.key, text)
                                        if (!result.ok) {
                                            appWindow.showNotice("입력을 확인하세요", result.message, "error")
                                            text = modelData.value
                                        }
                                    }
                                }
                            }

                            Component {
                                id: unitBox
                                ComboBox {
                                    model: modelData.choices
                                    currentIndex: Math.max(0, modelData.choices.indexOf(modelData.value))
                                    displayText: currentText.length ? currentText : "장비 선택"
                                    onActivated: {
                                        if (currentText === modelData.value)
                                            return
                                        var result = workspace.setSetupValue(modelData.key, currentText)
                                        if (!result.ok)
                                            appWindow.showNotice("입력을 확인하세요", result.message, "error")
                                    }
                                }
                            }

                            Component {
                                id: readOnlyBox
                                TextField {
                                    text: modelData.value
                                    readOnly: true
                                    color: Theme.muted
                                }
                            }
                        }

                        Text {
                            visible: modelData.issue.length > 0
                            text: "⚠ " + modelData.issue
                            color: Theme.danger
                            font.pixelSize: 11
                        }

                        Item { Layout.fillWidth: true }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.leftMargin: 160
                        visible: modelData.detail.length > 0
                        text: modelData.detail
                        color: Theme.muted
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        Card {
            Layout.fillWidth: true
            title: "이 프로젝트 요약"

            Text {
                Layout.fillWidth: true
                text: workspace.summaryText
                color: Theme.ink
                font.pixelSize: 12
                font.family: "Menlo"
                wrapMode: Text.WordWrap
            }
        }
    }
}
