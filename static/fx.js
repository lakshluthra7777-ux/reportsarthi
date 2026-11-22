// ReportSaathi interface effects. Plain JavaScript, no libraries.
// Each block looks for elements with a certain class or data- attribute, so a page
// only gets the effects it asks for.

(function () {
    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---------- Theme switch (🌙 / ☀️) ----------
    // The choice is saved in localStorage so it stays after a reload. The <head> of
    // base.html applies it before the page is drawn, so there is no flash.
    var toggle = document.getElementById("theme-toggle");
    function currentTheme() {
        var set = document.documentElement.dataset.theme;
        if (set) return set;
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    function showIcon() {
        if (toggle) toggle.textContent = currentTheme() === "dark" ? "☀️" : "🌙";
    }
    if (toggle) {
        showIcon();
        toggle.addEventListener("click", function () {
            var next = currentTheme() === "dark" ? "light" : "dark";
            document.documentElement.dataset.theme = next;
            try { localStorage.setItem("theme", next); } catch (e) { /* storage blocked: fine */ }
            showIcon();
        });
    }

    // ---------- Scroll reveal ----------
    // IntersectionObserver tells us when an element scrolls into view.
    var revealItems = document.querySelectorAll(".reveal");
    if (reduceMotion || !("IntersectionObserver" in window)) {
        revealItems.forEach(function (el) { el.classList.add("visible"); });
    } else {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.08 });
        revealItems.forEach(function (el, index) {
            el.style.transitionDelay = Math.min(index % 8, 7) * 60 + "ms";  // small stagger
            observer.observe(el);
        });
    }

    // ---------- Count-up numbers: <strong data-count="12">0</strong> ----------
    document.querySelectorAll("[data-count]").forEach(function (el) {
        var target = Number(el.dataset.count);
        var suffix = el.dataset.suffix || "";
        if (reduceMotion) { el.textContent = target + suffix; return; }
        var start = null;
        function step(time) {
            if (start === null) start = time;
            var progress = Math.min((time - start) / 1200, 1);
            var eased = 1 - Math.pow(1 - progress, 3);  // fast at first, slows down at the end
            el.textContent = Math.round(target * eased) + suffix;
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    });

    // ---------- 3D tilt on hover ----------
    if (!reduceMotion && window.matchMedia("(hover: hover)").matches) {
        document.querySelectorAll(".tilt").forEach(function (card) {
            card.addEventListener("mousemove", function (event) {
                var box = card.getBoundingClientRect();
                var x = (event.clientX - box.left) / box.width - 0.5;   // -0.5 .. 0.5
                var y = (event.clientY - box.top) / box.height - 0.5;
                card.style.setProperty("--ry", x * 10 + "deg");
                card.style.setProperty("--rx", -y * 10 + "deg");
            });
            card.addEventListener("mouseleave", function () {
                card.style.setProperty("--ry", "0deg");
                card.style.setProperty("--rx", "0deg");
            });
        });
    }

    // ---------- AI scanning overlay while a report is being read ----------
    var scanForm = document.querySelector("form[data-scan]");
    var overlay = document.getElementById("scan-overlay");
    if (scanForm && overlay) {
        scanForm.addEventListener("submit", function () {
            var steps = [
                "📄 Opening your report...",
                "🔍 Finding every test value...",
                "📏 Checking normal ranges...",
                "🧠 Writing a simple explanation...",
                "👩‍⚕️ Preparing questions for your doctor...",
                "✨ Almost done...",
            ];
            var text = overlay.querySelector(".scan-step");
            var bar = overlay.querySelector(".scan-progress div");
            var i = 0;
            overlay.classList.add("show");
            text.textContent = steps[0];
            // The AI usually takes 20-40 seconds; move the bar towards 95% over ~40 s.
            var percent = 0;
            setInterval(function () {
                percent = Math.min(percent + (95 - percent) * 0.06, 95);
                bar.style.width = percent + "%";
            }, 1000);
            setInterval(function () {
                i = Math.min(i + 1, steps.length - 1);
                text.textContent = steps[i];
            }, 6000);
        });
    }

    // ---------- 🔊 Listen: read text aloud with the browser's built-in voices ----------
    document.querySelectorAll("[data-speak]").forEach(function (button) {
        if (!("speechSynthesis" in window)) { button.hidden = true; return; }
        var label = button.innerHTML;
        button.addEventListener("click", function () {
            if (speechSynthesis.speaking) {
                speechSynthesis.cancel();
                return;
            }
            var target = document.querySelector(button.dataset.speak);
            var utterance = new SpeechSynthesisUtterance(target.innerText);
            utterance.lang = button.dataset.lang || "en-IN";
            utterance.rate = 0.95;
            utterance.onstart = function () {
                button.classList.add("speaking");
                button.innerHTML = "⏹️ Stop";
            };
            utterance.onend = utterance.onerror = function () {
                button.classList.remove("speaking");
                button.innerHTML = label;
            };
            speechSynthesis.speak(utterance);
        });
    });
})();
