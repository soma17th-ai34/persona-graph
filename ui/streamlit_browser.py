from __future__ import annotations

import streamlit.components.v1 as components


def scroll_chat_to_bottom() -> None:
    components.html(
        """
<script>
const root = window.parent.document;
const anchor = root.getElementById("pg-chat-bottom");
if (anchor) {
  anchor.scrollIntoView({ block: "end", behavior: "smooth" });
}
</script>
""",
        height=0,
        width=0,
    )

def install_composer_autosize() -> None:
    components.html(
        """
<script>
(function () {
  const root = window.parent.document;
  const minHeight = 41;
  const maxHeight = 132;

  function composerTextareas() {
    return root.querySelectorAll(
      'div[data-testid="stForm"]:has(.pg-empty-composer-anchor) textarea, ' +
      'div[data-testid="stForm"]:has(.pg-docked-composer-anchor) textarea'
    );
  }

  function composerForms() {
    return root.querySelectorAll(
      'div[data-testid="stForm"]:has(.pg-empty-composer-anchor), ' +
      'div[data-testid="stForm"]:has(.pg-docked-composer-anchor)'
    );
  }

  function hideFocusedSubmitHint() {
    composerForms().forEach(function (form) {
      form.querySelectorAll("div, span, small, p").forEach(function (node) {
        const text = (node.textContent || "").replace(/\\s+/g, " ").trim();
        if (/^Press\\s+(?:⌘|Cmd|Command|Ctrl|Control)\\s*\\+?\\s*Enter\\s+to\\s+submit\\s+form$/i.test(text)) {
          node.style.setProperty("display", "none", "important");
        }
      });
    });
  }

  function resize(textarea) {
    textarea.style.setProperty("height", minHeight + "px", "important");
    const nextHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight));
    textarea.style.setProperty("height", nextHeight + "px", "important");
    textarea.style.setProperty(
      "overflow-y",
      textarea.scrollHeight > maxHeight ? "auto" : "hidden",
      "important"
    );
  }

  function wire(textarea) {
    if (textarea.dataset.pgComposerAutosize !== "1") {
      textarea.dataset.pgComposerAutosize = "1";
      textarea.addEventListener("input", function () {
        resize(textarea);
      });
      textarea.addEventListener("focus", function () {
        window.setTimeout(hideFocusedSubmitHint, 0);
        window.setTimeout(hideFocusedSubmitHint, 80);
      });
      textarea.addEventListener("keydown", function (event) {
        if (
          event.key !== "Enter" ||
          event.shiftKey ||
          event.isComposing ||
          event.keyCode === 229
        ) {
          return;
        }

        const form = textarea.closest('div[data-testid="stForm"]');
        const submitButton = form && form.querySelector('div[data-testid="stFormSubmitButton"] button');
        if (!submitButton || submitButton.disabled) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();
        submitButton.click();
      });
    }
    resize(textarea);
  }

  function resizeAll() {
    composerTextareas().forEach(wire);
    hideFocusedSubmitHint();
  }

  if (!window.parent.__pgComposerAutosizeInstalled) {
    window.parent.__pgComposerAutosizeInstalled = true;
    window.parent.addEventListener("resize", resizeAll);
    const observer = new MutationObserver(resizeAll);
    observer.observe(root.body, { childList: true, subtree: true });
  }

  window.setTimeout(resizeAll, 0);
  window.setTimeout(resizeAll, 120);
})();
</script>
""",
        height=0,
        width=0,
    )

def install_config_start_hide() -> None:
    components.html(
        """
<script>
(function () {
  const root = window.parent.document;

  function configMessages() {
    return root.querySelectorAll('div[data-testid="stChatMessage"]:has(.pg-config-bubble-anchor)');
  }

  function hideConfigMessages() {
    configMessages().forEach(function (message) {
      message.style.setProperty("display", "none", "important");
    });
  }

  function wireStartButtons() {
    configMessages().forEach(function (message) {
      message.querySelectorAll('button').forEach(function (button) {
        const label = (button.textContent || "").trim();
        if (!label.includes("시작하기") && !label.includes("이 설정으로 시작")) {
          return;
        }
        if (button.dataset.pgConfigStartHide === "1") {
          return;
        }
        button.dataset.pgConfigStartHide = "1";
        button.addEventListener("click", function () {
          window.parent.__pgConfigStartInFlight = true;
          hideConfigMessages();
          window.parent.setTimeout(hideConfigMessages, 0);
          window.parent.setTimeout(hideConfigMessages, 120);
          window.parent.setTimeout(function () {
            window.parent.__pgConfigStartInFlight = false;
          }, 5000);
        });
      });
    });
    if (window.parent.__pgConfigStartInFlight) {
      hideConfigMessages();
    }
  }

  if (!window.parent.__pgConfigStartHideInstalled) {
    window.parent.__pgConfigStartHideInstalled = true;
    const observer = new MutationObserver(wireStartButtons);
    observer.observe(root.body, { childList: true, subtree: true });
  }

  wireStartButtons();
})();
</script>
""",
        height=0,
        width=0,
    )
