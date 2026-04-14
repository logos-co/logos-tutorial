import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""
    property string versionFromEvent: ""

    // Subscribe to "versionReady" events pushed from calc_module.
    Component.onCompleted: {
        if (typeof logos !== "undefined" && logos.onModuleEvent)
            logos.onModuleEvent("calc_module", "versionReady")
    }

    Connections {
        target: typeof logos !== "undefined" ? logos : null
        function onModuleEventReceived(moduleName, eventName, data) {
            if (eventName === "versionReady")
                root.versionFromEvent = data[0]
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // ── Title ──────────────────────────────────────────────
        Text {
            text: "Logos Calculator"
            font.pixelSize: 20
            font.weight: Font.DemiBold
            color: "#ffffff"
            Layout.alignment: Qt.AlignHCenter
        }

        // ── Pattern 1: Direct call (request -> response) ──────
        Text {
            text: "Direct calls (logos.callModule -> returns result)"
            color: "#8b949e"
            font.pixelSize: 12
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField {
                id: inputA
                placeholderText: "a"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }

            TextField {
                id: inputB
                placeholderText: "b"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }

            Button {
                text: "Add"
                onClicked: callTwoOp("add", inputA.text, inputB.text)
            }

            Button {
                text: "Multiply"
                onClicked: callTwoOp("multiply", inputA.text, inputB.text)
            }
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField {
                id: inputN
                placeholderText: "n"
                Layout.preferredWidth: 80
                validator: IntValidator { bottom: 0 }
            }

            Button {
                text: "Factorial"
                onClicked: callOneOp("factorial", inputN.text)
            }

            Button {
                text: "Fibonacci"
                onClicked: callOneOp("fibonacci", inputN.text)
            }

            Button {
                text: "libcalc version"
                onClicked: callModule("libVersion", [])
            }
        }

        // Direct call result
        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: root.errorText.length > 0 ? "#3d1a1a" : "#1a2d1a"
            radius: 8

            Text {
                anchors.centerIn: parent
                text: root.errorText.length > 0 ? root.errorText
                        : (root.result.length > 0 ? root.result : "Enter values and press a button")
                color: root.errorText.length > 0 ? "#f85149" : "#56d364"
                font.pixelSize: 15
            }
        }

        // ── Pattern 2: Event-based (fire-and-forget -> event) ─
        Text {
            text: "Event-based (fire-and-forget call -> result via event)"
            color: "#8b949e"
            font.pixelSize: 12
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            Button {
                text: "libcalc version (event)"
                onClicked: {
                    if (typeof logos !== "undefined" && logos.callModule)
                        logos.callModule("calc_module", "libVersionNotify", [])
                }
            }
        }

        // Event result
        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: "#1a1a2d"
            radius: 8

            Text {
                anchors.centerIn: parent
                text: root.versionFromEvent.length > 0
                      ? ("Version (via event): " + root.versionFromEvent)
                      : "Press the event button — result arrives via event"
                color: "#7ab8ff"
                font.pixelSize: 15
            }
        }

        Item { Layout.fillHeight: true }
    }

    // ── Direct call helpers ───────────────────────────────────

    function callModule(method, args) {
        root.errorText = ""
        root.result = ""

        if (typeof logos === "undefined" || !logos.callModule) {
            root.errorText = "Logos bridge not available"
            return
        }

        root.result = String(logos.callModule("calc_module", method, args))
    }

    function callTwoOp(method, a, b) {
        if (a === "" || b === "") { root.errorText = "Enter values for a and b"; return }
        callModule(method, [parseInt(a), parseInt(b)])
    }

    function callOneOp(method, n) {
        if (n === "") { root.errorText = "Enter a value for n"; return }
        callModule(method, [parseInt(n)])
    }
}
