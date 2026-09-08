import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 5. 내보내기 — the ladder, and each output path with what is blocking it.
Item {
    id: page
    property var options: []
    property var stages: []
    property var review: ({})

    function reload() {
        options = workspace.releaseOptions()
        stages = workspace.ladder()
        review = workspace.reviewState()
    }

    Connections {
        target: workspace
        function onChanged() { page.reload() }
    }
    Component.onCompleted: reload()

    ScrollView {
        id: exportScroll
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: exportScroll.availableWidth
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Repeater {
                    model: page.stages
                    RowLayout {
                        required property var modelData
                        required property int index
                        spacing: 6
                        Rectangle {
                            radius: Theme.radius
                            color: modelData.reached ? Theme.accent : Theme.panel
                            border.color: modelData.reached ? Theme.accent : Theme.line
                            implicitWidth: stageLabel.implicitWidth + 22
                            implicitHeight: 32
                            Text {
                                id: stageLabel
                                anchors.centerIn: parent
                                text: (modelData.reached ? "✔ " : "") + modelData.label
                                color: modelData.reached ? "#ffffff" : Theme.muted
                                font.pixelSize: 12
                                font.bold: modelData.reached
                            }
                        }
                        Text {
                            visible: index < page.stages.length - 1
                            text: "→"
                            color: Theme.muted
                        }
                    }
                }
                Item { Layout.fillWidth: true }
            }

            Text {
                text: "초안 저장은 언제나 가능합니다. 아래로 갈수록 더 많은 확인이 필요합니다."
                color: Theme.muted
                font.pixelSize: 12
            }

            Repeater {
                model: page.options

                Card {
                    required property var modelData
                    Layout.fillWidth: true

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: modelData.allowed ? "🔓" : "🔒"
                            font.pixelSize: 16
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.title
                                color: modelData.danger && modelData.allowed ? Theme.warn : Theme.ink
                                font.pixelSize: 14
                                font.bold: true
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                text: modelData.description
                                color: Theme.muted
                                font.pixelSize: 11
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                        }
                        Button {
                            text: modelData.allowed ? "실행" : "잠김"
                            enabled: modelData.allowed
                            onClicked: appWindow.runExport(modelData.kind)
                        }
                    }

                    Repeater {
                        model: modelData.blockers
                        Text {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.leftMargin: 26
                            text: "· " + modelData
                            color: Theme.danger
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        visible: !modelData.allowed && modelData.nextAction.length > 0
                        text: "다음 단계: " + modelData.nextAction
                        color: Theme.muted
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Card {
                Layout.fillWidth: true
                title: "확인 기록"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text { text: "검토자"; color: Theme.ink; font.pixelSize: 12 }
                    TextField {
                        id: reviewerField
                        Layout.preferredWidth: 160
                        placeholderText: "이름"
                        selectByMouse: true
                    }
                    Button {
                        text: "CTSPro 확인 완료로 기록"
                        onClicked: workspace.recordReview(reviewerField.text)
                    }
                    Button {
                        text: "장비 실행 승인 기록"
                        onClicked: appWindow.confirm(
                            "장비 실행 승인",
                            "이 스케줄을 장비에서 실행해도 된다고 기록합니다.\n" +
                            "CTSPro 에서 값이 모두 확인되었을 때만 진행하세요. 계속할까요?",
                            function () { workspace.recordApproval(reviewerField.text) })
                    }
                    Button {
                        text: "승인 해제"
                        onClicked: workspace.clearApprovals()
                    }
                    Item { Layout.fillWidth: true }
                }

                Text {
                    Layout.fillWidth: true
                    text: {
                        var parts = []
                        parts.push("CTSPro 확인: " + (page.review.ctsproReviewed
                            ? "완료 (" + page.review.ctsproReviewer + ")" : "없음"))
                        parts.push("장비 승인: " + (page.review.equipmentApproved
                            ? "완료 (" + page.review.equipmentApprovedBy + ")" : "없음"))
                        return parts.join("   |   ")
                    }
                    color: Theme.muted
                    font.pixelSize: 11
                }
            }

            Card {
                Layout.fillWidth: true
                title: "한국어 요약"

                Text {
                    Layout.fillWidth: true
                    text: workspace.summaryText
                    color: Theme.ink
                    font.pixelSize: 12
                    font.family: "Menlo"
                    wrapMode: Text.WordWrap
                }

                Button {
                    Layout.alignment: Qt.AlignRight
                    text: "요약 복사"
                    onClicked: workspace.copySummary()
                }
            }
        }
    }
}
