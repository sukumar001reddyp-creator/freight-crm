document.addEventListener(
    "DOMContentLoaded",
    function () {
        const sidebar =
            document.getElementById("sidebar");

        const menuToggle =
            document.getElementById("menuToggle");

        const sidebarClose =
            document.getElementById("sidebarClose");

        const sidebarOverlay =
            document.getElementById(
                "sidebarOverlay"
            );

        function openSidebar() {
            if (!sidebar) return;

            sidebar.classList.add("open");

            if (sidebarOverlay) {
                sidebarOverlay.classList.add(
                    "show"
                );
            }

            document.body.style.overflow =
                "hidden";
        }

        function closeSidebar() {
            if (!sidebar) return;

            sidebar.classList.remove("open");

            if (sidebarOverlay) {
                sidebarOverlay.classList.remove(
                    "show"
                );
            }

            document.body.style.overflow =
                "";
        }

        if (menuToggle) {
            menuToggle.addEventListener(
                "click",
                openSidebar
            );
        }

        if (sidebarClose) {
            sidebarClose.addEventListener(
                "click",
                closeSidebar
            );
        }

        if (sidebarOverlay) {
            sidebarOverlay.addEventListener(
                "click",
                closeSidebar
            );
        }

        window.addEventListener(
            "resize",
            function () {
                if (window.innerWidth > 920) {
                    closeSidebar();
                }
            }
        );

        const alertCloseButtons =
            document.querySelectorAll(
                ".alert-close"
            );

        alertCloseButtons.forEach(
            function (button) {
                button.addEventListener(
                    "click",
                    function () {
                        const alert =
                            button.closest(
                                ".app-alert"
                            );

                        if (alert) {
                            alert.remove();
                        }
                    }
                );
            }
        );

        const mgmtToggle =
            document.getElementById(
                "mgmtDropdownToggle"
            );

        const mgmtGroup =
            document.getElementById(
                "mgmtClientsGroup"
            );

        function toggleMgmtGroup(event) {
            if (event) {
                event.preventDefault();
            }

            if (!mgmtGroup || !mgmtToggle) return;

            const isOpen =
                mgmtGroup.classList.toggle(
                    "open"
                );

            mgmtToggle.setAttribute(
                "aria-expanded",
                isOpen ? "true" : "false"
            );
        }

        if (mgmtToggle) {
            mgmtToggle.addEventListener(
                "click",
                toggleMgmtGroup
            );

            mgmtToggle.addEventListener(
                "keydown",
                function (event) {
                    if (
                        event.key === "Enter" ||
                        event.key === " "
                    ) {
                        toggleMgmtGroup(event);
                    }
                }
            );
        }
    }
);