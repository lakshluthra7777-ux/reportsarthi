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
        // Same line icons as templates/_icons.html: a sun in dark mode (switch to light), else a moon.
        var sun = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/>' +
            '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
        var moon = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
        if (toggle) toggle.innerHTML = currentTheme() === "dark" ? sun : moon;
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
                "Opening your report",
                "Finding every test value",
                "Checking normal ranges",
                "Writing a simple explanation",
                "Preparing questions for your doctor",
                "Almost done",
            ];
            // "Buffering" emojis: one at a time, with a soft pop (see .loader-emoji in fx.css).
            var emojis = ["🧪", "🩸", "🔬", "🧬", "❤️", "🧠", "💊", "🩺"];
            // Short, true health facts to read while waiting.
            var facts = [
                ["🩸", "Red blood cells live about 120 days, which is why HbA1c shows your average sugar over roughly 3 months."],
                ["📏", "A “normal range” covers about 95% of healthy people, so 1 in 20 healthy people can be slightly outside it."],
                ["☀️", "Vitamin D deficiency is very common in India despite the sunshine, because of indoor lifestyles."],
                ["💧", "Being dehydrated can make values like haemoglobin and creatinine look higher than they really are."],
                ["🍽️", "A fasting test usually means no food for 8–12 hours. Plain water is allowed."],
                ["🦴", "About 99% of the calcium in your body is stored in your bones and teeth."],
                ["🫘", "Your kidneys filter roughly 180 litres of blood plasma every day."],
                ["❤️", "Your heart beats around 100,000 times a day."],
                ["🧪", "Different labs can use slightly different normal ranges, so always compare with the range printed on your report."],
                ["🍋", "Vitamin C helps your body absorb iron from plant foods like spinach and lentils."],
                ["🥛", "Vitamin B12 comes mainly from animal foods, so vegetarians are more likely to run low."],
                ["🦋", "TSH works in reverse: a high TSH usually means the thyroid is underactive."],
                ["📈", "One slightly-off value often matters less than the trend across several reports."],
                ["🧠", "The brain is about 2% of body weight but uses around 20% of the body's energy."],
            ];
            var stepText = overlay.querySelector(".scan-step");
            var bar = overlay.querySelector(".scan-progress div");
            var timer = overlay.querySelector(".scan-timer");
            var emoji = overlay.querySelector(".loader-emoji");
            var factEmoji = overlay.querySelector(".fact-emoji");
            var factText = overlay.querySelector(".fact-text");
            var fact = overlay.querySelector(".fact");

            var step = 0, tick = 0, emojiIndex = 0;
            var factIndex = Math.floor(Math.random() * facts.length);  // start somewhere random
            function showFact() {
                factEmoji.textContent = facts[factIndex][0];
                factText.textContent = facts[factIndex][1];
                fact.classList.remove("fade-in");
                void fact.offsetWidth;          // restart the CSS animation
                fact.classList.add("fade-in");
            }

            overlay.classList.add("show");
            stepText.textContent = steps[0];
            showFact();

            setInterval(function () {           // every second: timer + progress bar
                tick++;
                timer.textContent = Math.floor(tick / 60) + ":" + String(tick % 60).padStart(2, "0");
                // The AI usually takes 20-40 seconds; ease the bar towards 95%.
                bar.style.width = Math.min(95, 95 * (1 - Math.exp(-tick / 18))) + "%";
                if (tick % 6 === 0) {           // every 6 s: next step
                    step = Math.min(step + 1, steps.length - 1);
                    stepText.textContent = steps[step];
                }
                if (tick % 7 === 0) {           // every 7 s: next fact
                    factIndex = (factIndex + 1) % facts.length;
                    showFact();
                }
            }, 1000);

            setInterval(function () {           // every 1.2 s: next buffering emoji
                emojiIndex = (emojiIndex + 1) % emojis.length;
                emoji.textContent = emojis[emojiIndex];
                emoji.classList.remove("pop");
                void emoji.offsetWidth;
                emoji.classList.add("pop");
            }, 1200);
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
                button.innerHTML = "Stop reading";
            };
            utterance.onend = utterance.onerror = function () {
                button.classList.remove("speaking");
                button.innerHTML = label;
            };
            speechSynthesis.speak(utterance);
        });
    });
})();
