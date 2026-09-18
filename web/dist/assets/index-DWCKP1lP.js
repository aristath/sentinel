const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/dist-qUpxMwR-.js","assets/dist-CzEUVXDC.js","assets/dist-CFtxRP70.js","assets/dist-n09HnSQH.js","assets/dist-CtvrPQL3.js","assets/dist-BtjFFX5g.js","assets/dist-Dp7zcg8q.js","assets/dist-CWt5MqEz.js","assets/dist-D8zCp1Lk.js","assets/dist-BhbiT-ju.js","assets/dist-DGm0tJyr.js"])))=>i.map(i=>d[i]);
//#region \0vite/modulepreload-polyfill.js
(function polyfill() {
	const relList = document.createElement("link").relList;
	if (relList && relList.supports && relList.supports("modulepreload")) return;
	for (const link of document.querySelectorAll("link[rel=\"modulepreload\"]")) processPreload(link);
	new MutationObserver((mutations) => {
		for (const mutation of mutations) {
			if (mutation.type !== "childList") continue;
			for (const node of mutation.addedNodes) if (node.tagName === "LINK" && node.rel === "modulepreload") processPreload(node);
		}
	}).observe(document, {
		childList: true,
		subtree: true
	});
	function getFetchOpts(link) {
		const fetchOpts = {};
		if (link.integrity) fetchOpts.integrity = link.integrity;
		if (link.referrerPolicy) fetchOpts.referrerPolicy = link.referrerPolicy;
		if (link.crossOrigin === "use-credentials") fetchOpts.credentials = "include";
		else if (link.crossOrigin === "anonymous") fetchOpts.credentials = "omit";
		else fetchOpts.credentials = "same-origin";
		return fetchOpts;
	}
	function processPreload(link) {
		if (link.ep) return;
		link.ep = true;
		const fetchOpts = getFetchOpts(link);
		fetch(link.href, fetchOpts);
	}
})();
//#endregion
//#region ../../teract/src/tui-element.js
var TuiElement = class extends HTMLElement {
	connectedCallback() {
		this.render();
	}
	attributeChangedCallback() {
		if (this.isConnected) this.render();
	}
	escape(value) {
		return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll("\"", "&quot;").replaceAll("'", "&#39;");
	}
	render() {}
};
//#endregion
//#region ../../teract/src/tui-flex.js
var alignments = {
	start: "flex-start",
	center: "center",
	end: "flex-end",
	baseline: "baseline",
	stretch: "stretch"
};
var justifications = {
	start: "flex-start",
	center: "center",
	end: "flex-end",
	between: "space-between",
	around: "space-around",
	evenly: "space-evenly"
};
var TuiFlex = class extends TuiElement {
	static observedAttributes = [
		"direction",
		"align",
		"justify",
		"wrap"
	];
	get direction() {
		return this.getAttribute("direction") === "column" ? "column" : "row";
	}
	get align() {
		return alignments[this.getAttribute("align")] || "stretch";
	}
	get justify() {
		return justifications[this.getAttribute("justify")] || "flex-start";
	}
	get wrap() {
		return this.hasAttribute("wrap") ? "wrap" : "nowrap";
	}
	render() {
		this.style.display = "flex";
		this.style.flexDirection = this.direction;
		this.style.alignItems = this.align;
		this.style.justifyContent = this.justify;
		this.style.flexWrap = this.wrap;
	}
};
customElements.define("tui-flex", TuiFlex);
//#endregion
//#region ../../teract/src/tui-bar.js
var TuiBar = class extends TuiElement {
	static observedAttributes = ["height"];
	get height() {
		const height = Number(this.getAttribute("height"));
		return Number.isInteger(height) && height > 0 ? height : 1;
	}
	render() {
		this.style.display = "block";
		this.style.minHeight = `${this.height}lh`;
		this.style.color = "var(--tui-background)";
		this.style.background = "var(--tui-color)";
	}
};
customElements.define("tui-bar", TuiBar);
//#endregion
//#region ../../teract/src/tui-box.js
var borders = {
	single: {
		topLeft: "┌",
		topRight: "┐",
		bottomLeft: "└",
		bottomRight: "┘",
		horizontal: "─",
		vertical: "│"
	},
	double: {
		topLeft: "╔",
		topRight: "╗",
		bottomLeft: "╚",
		bottomRight: "╝",
		horizontal: "═",
		vertical: "║"
	}
};
var TuiBox = class extends TuiElement {
	static observedAttributes = ["border", "heading"];
	#top;
	#topLeft;
	#topFill;
	#body;
	#left;
	#content;
	#right;
	#bottom;
	#bottomFill;
	#resizeObserver;
	#childObserver;
	#generatedLabel;
	get border() {
		return this.getAttribute("border") === "double" ? "double" : "single";
	}
	get heading() {
		return this.getAttribute("heading") || "";
	}
	connectedCallback() {
		super.connectedCallback();
		if (typeof ResizeObserver !== "undefined") {
			this.#resizeObserver = new ResizeObserver(() => this.#syncBorders());
			this.#resizeObserver.observe(this.#top);
			this.#resizeObserver.observe(this.#content);
		}
		this.#childObserver = new MutationObserver(() => this.#moveLooseChildren());
		this.#childObserver.observe(this, { childList: true });
		queueMicrotask(() => this.#syncBorders());
	}
	disconnectedCallback() {
		this.#resizeObserver?.disconnect();
		this.#childObserver?.disconnect();
	}
	render() {
		if (!this.#content) this.#mount();
		this.#renderBorder();
		this.#syncAccessibleName();
	}
	#mount() {
		const authoredNodes = [...this.childNodes];
		this.style.display = "block";
		this.style.minWidth = "0";
		this.style.overflowWrap = "anywhere";
		this.innerHTML = `
			<div data-tui-box-top aria-hidden="true"></div>
			<div data-tui-box-body>
				<span data-tui-box-left aria-hidden="true"></span>
				<div data-tui-box-content></div>
				<span data-tui-box-right aria-hidden="true"></span>
			</div>
			<div data-tui-box-bottom aria-hidden="true"></div>
		`;
		this.#top = this.querySelector("[data-tui-box-top]");
		this.#body = this.querySelector("[data-tui-box-body]");
		this.#left = this.querySelector("[data-tui-box-left]");
		this.#content = this.querySelector("[data-tui-box-content]");
		this.#right = this.querySelector("[data-tui-box-right]");
		this.#bottom = this.querySelector("[data-tui-box-bottom]");
		this.#top.style.cssText = "display:flex;min-width:0;overflow:hidden;white-space:nowrap;contain:inline-size";
		this.#body.style.cssText = "display:grid;grid-template-columns:2ch minmax(0,1fr) 2ch;align-items:stretch;min-width:0";
		this.#left.style.cssText = "overflow:hidden;white-space:pre;line-height:inherit";
		this.#content.style.cssText = "min-width:0;overflow-wrap:anywhere";
		this.#right.style.cssText = "overflow:hidden;white-space:pre;line-height:inherit";
		this.#bottom.style.cssText = "display:flex;min-width:0;overflow:hidden;white-space:nowrap;contain:inline-size";
		this.#content.append(...authoredNodes);
	}
	#renderBorder() {
		const glyphs = borders[this.border];
		this.#top.replaceChildren();
		this.#topLeft = this.#span(glyphs.topLeft);
		this.#topFill = this.#span(glyphs.horizontal, true);
		this.#top.append(this.#topLeft, this.#span(this.heading ? glyphs.horizontal : ""), this.#span(this.heading ? `\u00a0${this.heading}\u00a0` : ""), this.#topFill, this.#span(glyphs.topRight));
		this.#bottom.replaceChildren();
		this.#bottomFill = this.#span(glyphs.horizontal, true);
		this.#bottom.append(this.#span(glyphs.bottomLeft), this.#bottomFill, this.#span(glyphs.bottomRight));
		this.#syncBorders();
	}
	#span(text, flexible = false) {
		const span = document.createElement("span");
		span.textContent = text;
		span.style.display = "block";
		span.style.whiteSpace = "nowrap";
		if (flexible) {
			span.style.flex = "1 1 0";
			span.style.minWidth = "0";
			span.style.overflow = "hidden";
		} else span.style.flex = "0 0 auto";
		return span;
	}
	#syncBorders() {
		if (!this.#top || !this.#content) return;
		const topBounds = this.#top.getBoundingClientRect();
		const glyphWidth = this.#topLeft.getBoundingClientRect().width;
		const horizontalColumns = glyphWidth > 0 ? Math.max(1, Math.ceil(topBounds.width / glyphWidth)) : 1;
		const horizontal = borders[this.border].horizontal.repeat(horizontalColumns);
		this.#topFill.textContent = horizontal;
		this.#bottomFill.textContent = horizontal;
		const lineHeight = topBounds.height;
		const contentHeight = this.#content.getBoundingClientRect().height;
		const rows = lineHeight > 0 ? Math.max(1, Math.ceil(contentHeight / lineHeight - .01)) : 1;
		const vertical = borders[this.border].vertical;
		this.#left.textContent = Array.from({ length: rows }, () => `${vertical}\u00a0`).join("\n");
		this.#right.textContent = Array.from({ length: rows }, () => `\u00a0${vertical}`).join("\n");
	}
	#moveLooseChildren() {
		const internalNodes = /* @__PURE__ */ new Set([
			this.#top,
			this.#body,
			this.#bottom
		]);
		const looseNodes = [...this.childNodes].filter((node) => !internalNodes.has(node));
		if (looseNodes.length > 0) this.#content.append(...looseNodes);
	}
	#syncAccessibleName() {
		if (!this.hasAttribute("role")) this.setAttribute("role", "group");
		const currentLabel = this.getAttribute("aria-label");
		if (this.heading && (!currentLabel || currentLabel === this.#generatedLabel)) {
			this.setAttribute("aria-label", this.heading);
			this.#generatedLabel = this.heading;
		} else if (!this.heading && currentLabel === this.#generatedLabel) {
			this.removeAttribute("aria-label");
			this.#generatedLabel = void 0;
		}
	}
};
customElements.define("tui-box", TuiBox);
//#endregion
//#region ../../teract/src/tui-button.js
var TuiButton = class extends TuiElement {
	state = {
		active: false,
		focus: false,
		hover: false
	};
	static observedAttributes = [
		"aria-controls",
		"aria-expanded",
		"aria-label",
		"disabled",
		"inverted",
		"name",
		"type",
		"value",
		"variant"
	];
	connectedCallback() {
		super.connectedCallback();
	}
	get type() {
		const type = this.getAttribute("type");
		return type === "submit" || type === "reset" ? type : "button";
	}
	get variant() {
		const variant = this.getAttribute("variant");
		return variant === "success" || variant === "warning" || variant === "error" ? variant : "default";
	}
	get marker() {
		return this.variant === "success" ? "+ " : this.variant === "warning" ? "! " : this.variant === "error" ? "x " : "";
	}
	get variantColor() {
		return this.variant === "default" ? "var(--tui-color)" : `var(--tui-${this.variant}-color)`;
	}
	get stateActive() {
		return !this.hasAttribute("disabled") && (this.state.hover || this.state.focus || this.state.active);
	}
	get inverted() {
		return this.hasAttribute("inverted") && this.variant === "default";
	}
	get buttonStyle() {
		const color = this.hasAttribute("disabled") ? "var(--tui-disabled-color)" : this.stateActive ? this.inverted ? "var(--tui-color)" : "var(--tui-focus-color)" : this.inverted ? "var(--tui-background)" : this.variantColor;
		const background = this.stateActive ? this.inverted ? "var(--tui-background)" : this.variant === "default" ? "var(--tui-focus-background)" : this.variantColor : "var(--tui-background-transparent)";
		const cursor = this.hasAttribute("disabled") ? "var(--tui-disabled-cursor)" : "var(--tui-action-cursor)";
		const textDecoration = this.stateActive && this.state.active ? "var(--tui-active-text-decoration)" : "var(--tui-text-decoration)";
		return [
			"all:var(--tui-reset-all)",
			"font-family:var(--tui-font-family)",
			`color:${color}`,
			`background:${background}`,
			`text-decoration:${textDecoration}`,
			`cursor:${cursor}`,
			"outline:var(--tui-focus-outline)"
		].join(";");
	}
	setState(name, value) {
		if (this.state[name] === value) return;
		this.state[name] = value;
		this.updateButtonStyle();
	}
	updateButtonStyle() {
		this.buttonElement?.setAttribute("style", this.buttonStyle);
	}
	setButtonAttribute(name, value) {
		if (value === null) this.buttonElement.removeAttribute(name);
		else this.buttonElement.setAttribute(name, value);
	}
	bindButtonEvents() {
		this.buttonElement.addEventListener("mouseenter", () => this.setState("hover", true));
		this.buttonElement.addEventListener("mouseleave", () => {
			this.setState("hover", false);
			this.setState("active", false);
		});
		this.buttonElement.addEventListener("focus", () => this.setState("focus", true));
		this.buttonElement.addEventListener("blur", () => {
			this.setState("focus", false);
			this.setState("active", false);
		});
		this.buttonElement.addEventListener("pointerdown", () => this.setState("active", true));
		this.buttonElement.addEventListener("pointerup", () => this.setState("active", false));
		this.buttonElement.addEventListener("pointercancel", () => this.setState("active", false));
		this.buttonElement.addEventListener("keydown", (event) => {
			if (event.key === " " || event.key === "Enter") this.setState("active", true);
		});
		this.buttonElement.addEventListener("keyup", () => this.setState("active", false));
	}
	mount() {
		const authoredNodes = [...this.childNodes];
		this.state.active = false;
		this.state.focus = false;
		this.state.hover = false;
		this.innerHTML = `
			<button>
				<span aria-hidden="true">[</span><span data-tui-button-marker aria-hidden="true"></span><span data-tui-button-content></span><span aria-hidden="true">]</span>
			</button>
		`;
		this.buttonElement = this.querySelector("button");
		this.markerElement = this.querySelector("[data-tui-button-marker]");
		this.contentElement = this.querySelector("[data-tui-button-content]");
		this.contentElement.append(...authoredNodes);
		this.bindButtonEvents();
	}
	updateButton() {
		this.buttonElement.type = this.type;
		this.buttonElement.disabled = this.hasAttribute("disabled");
		this.setButtonAttribute("name", this.getAttribute("name"));
		this.setButtonAttribute("value", this.getAttribute("value"));
		this.setButtonAttribute("aria-controls", this.getAttribute("aria-controls"));
		this.setButtonAttribute("aria-expanded", this.getAttribute("aria-expanded"));
		this.setButtonAttribute("aria-label", this.getAttribute("aria-label"));
		this.markerElement.textContent = this.marker;
		this.updateButtonStyle();
	}
	render() {
		if (!this.buttonElement) this.mount();
		this.updateButton();
	}
};
customElements.define("tui-button", TuiButton);
//#endregion
//#region ../../teract/src/tui-modal.js
var modalCount = 0;
var TuiModal = class extends TuiElement {
	static observedAttributes = [
		"aria-label",
		"heading",
		"open"
	];
	#dialog;
	#heading;
	#content;
	#closeButton;
	#childObserver;
	#headingId = `tui-modal-heading-${++modalCount}`;
	get open() {
		return this.hasAttribute("open");
	}
	set open(value) {
		this.toggleAttribute("open", Boolean(value));
	}
	get heading() {
		return this.getAttribute("heading") || "";
	}
	get returnValue() {
		return this.#dialog?.returnValue || "";
	}
	connectedCallback() {
		super.connectedCallback();
		this.#childObserver = new MutationObserver(() => this.#moveLooseChildren());
		this.#childObserver.observe(this, { childList: true });
		this.#syncOpen();
	}
	disconnectedCallback() {
		this.#childObserver?.disconnect();
	}
	showModal() {
		this.setAttribute("open", "");
		this.#syncOpen();
	}
	close(returnValue = "") {
		if (this.#dialog?.open) this.#dialog.close(returnValue);
		this.removeAttribute("open");
		if (this.#dialog) this.#dialog.style.display = "none";
	}
	render() {
		if (!this.#dialog) this.#mount();
		this.#syncLabel();
		this.#syncOpen();
	}
	#mount() {
		const authoredNodes = [...this.childNodes];
		this.innerHTML = `
			<dialog>
				<div data-tui-modal-layout>
					<div data-tui-modal-header>
						<span data-tui-modal-heading></span>
						<span data-tui-modal-close></span>
					</div>
					<div data-tui-modal-content></div>
				</div>
			</dialog>
		`;
		this.#dialog = this.querySelector("dialog");
		this.#heading = this.querySelector("[data-tui-modal-heading]");
		this.#content = this.querySelector("[data-tui-modal-content]");
		const closeSlot = this.querySelector("[data-tui-modal-close]");
		this.#closeButton = document.createElement("tui-button");
		this.#closeButton.setAttribute("aria-label", "Close");
		this.#closeButton.textContent = "×";
		closeSlot.append(this.#closeButton);
		this.#dialog.style.cssText = [
			"all:var(--tui-reset-all)",
			"position:fixed",
			"inset:0",
			"width:100vw",
			"height:100dvh",
			"max-width:100vw",
			"max-height:100dvh",
			"color:var(--tui-color)",
			"background:var(--tui-background)",
			"font-family:var(--tui-font-family)",
			"overflow:hidden"
		].join(";");
		this.querySelector("[data-tui-modal-layout]").style.cssText = "display:flex;flex-direction:column;width:100%;height:100%;min-width:0;min-height:0";
		this.querySelector("[data-tui-modal-header]").style.cssText = "display:flex;align-items:baseline;justify-content:space-between;flex:0 0 auto;min-width:0";
		this.#heading.style.cssText = "min-width:0;overflow-wrap:anywhere";
		closeSlot.style.cssText = "flex:0 0 auto";
		this.#content.style.cssText = "flex:1 1 auto;min-width:0;min-height:0;overflow:auto;overflow-wrap:anywhere";
		this.#content.append(...authoredNodes);
		this.#closeButton.addEventListener("click", () => this.#requestClose());
		this.#dialog.addEventListener("cancel", (event) => {
			event.preventDefault();
			this.#requestClose();
		});
		this.#dialog.addEventListener("close", () => {
			if (!this.#dialog.open) {
				this.#dialog.style.display = "none";
				this.removeAttribute("open");
			}
			this.dispatchEvent(new Event("close"));
		});
	}
	#requestClose() {
		const cancelEvent = new Event("cancel", { cancelable: true });
		if (this.dispatchEvent(cancelEvent)) this.close();
	}
	#syncLabel() {
		this.#heading.textContent = this.heading;
		this.#heading.hidden = !this.heading;
		if (this.heading) {
			this.#heading.id = this.#headingId;
			this.#dialog.setAttribute("aria-labelledby", this.#headingId);
			this.#dialog.removeAttribute("aria-label");
			return;
		}
		this.#heading.removeAttribute("id");
		this.#dialog.removeAttribute("aria-labelledby");
		this.#dialog.setAttribute("aria-label", this.getAttribute("aria-label") || "Modal");
	}
	#syncOpen() {
		if (!this.#dialog) return;
		if (this.open) {
			const shouldFocus = !this.#dialog.open;
			if (!this.#dialog.open) this.#dialog.showModal();
			this.#dialog.style.display = "flex";
			if (shouldFocus) this.#closeButton.querySelector("button")?.focus();
			return;
		}
		if (this.#dialog.open) this.#dialog.close();
		this.#dialog.style.display = "none";
	}
	#moveLooseChildren() {
		const looseNodes = [...this.childNodes].filter((node) => node !== this.#dialog);
		if (looseNodes.length > 0) this.#content.append(...looseNodes);
	}
};
customElements.define("tui-modal", TuiModal);
//#endregion
//#region ../../teract/src/tui-badge.js
var TuiBadge = class extends TuiElement {
	static observedAttributes = ["variant"];
	connectedCallback() {
		super.connectedCallback();
	}
	cacheContent() {
		if (this.content === void 0) this.content = this.textContent.trim();
	}
	get variant() {
		const variant = this.getAttribute("variant");
		return variant === "success" || variant === "warning" || variant === "error" ? variant : "default";
	}
	get variantColor() {
		return this.variant === "default" ? "var(--tui-focus-background)" : `var(--tui-${this.variant}-color)`;
	}
	get badgeStyle() {
		return [
			"font-family:var(--tui-font-family)",
			"color:var(--tui-focus-color)",
			`background:${this.variantColor}`
		].join(";");
	}
	render() {
		this.cacheContent();
		this.innerHTML = `
			<span style="${this.badgeStyle}">
				${this.escape(this.content)}
			</span>
		`;
	}
};
var TuiTag = class extends TuiBadge {};
customElements.define("tui-badge", TuiBadge);
customElements.define("tui-tag", TuiTag);
//#endregion
//#region ../../teract/src/tui-text.js
var TuiText = class extends TuiElement {
	static observedAttributes = ["variant"];
	get variant() {
		const variant = this.getAttribute("variant");
		return variant === "success" || variant === "warning" || variant === "error" ? variant : "default";
	}
	get color() {
		return this.variant === "default" ? "var(--tui-color)" : `var(--tui-${this.variant}-color)`;
	}
	render() {
		this.style.fontFamily = "var(--tui-font-family)";
		this.style.color = this.color;
	}
};
customElements.define("tui-text", TuiText);
//#endregion
//#region ../../teract/src/tui-toggle.js
var TuiToggle = class extends TuiElement {
	state = {
		active: false,
		focus: false,
		hover: false
	};
	static observedAttributes = [
		"aria-label",
		"checked",
		"disabled",
		"name",
		"value"
	];
	connectedCallback() {
		super.connectedCallback();
	}
	attributeChangedCallback(name, oldValue, newValue) {
		if (name === "aria-label" && this.toggleElement && oldValue !== newValue) {
			if (newValue === null) this.toggleElement.removeAttribute(name);
			else this.toggleElement.setAttribute(name, newValue);
			return;
		}
		super.attributeChangedCallback();
	}
	get checked() {
		return this.hasAttribute("checked");
	}
	get blocks() {
		return this.checked ? "░░█" : "▓░░";
	}
	get stateActive() {
		return !this.hasAttribute("disabled") && (this.state.hover || this.state.focus || this.state.active);
	}
	get toggleColor() {
		return this.hasAttribute("disabled") ? "var(--tui-disabled-color)" : this.checked ? "var(--tui-success-color)" : "var(--tui-color)";
	}
	get toggleBackground() {
		return this.stateActive ? this.checked ? "var(--tui-success-color)" : "var(--tui-focus-background)" : "var(--tui-background-transparent)";
	}
	get toggleStyle() {
		const color = this.stateActive ? "var(--tui-focus-color)" : this.toggleColor;
		const cursor = this.hasAttribute("disabled") ? "var(--tui-disabled-cursor)" : "var(--tui-action-cursor)";
		const textDecoration = this.stateActive && this.state.active ? "var(--tui-active-text-decoration)" : "var(--tui-text-decoration)";
		return [
			"all:var(--tui-reset-all)",
			"font-family:var(--tui-font-family)",
			`color:${color}`,
			`background:${this.toggleBackground}`,
			`text-decoration:${textDecoration}`,
			`cursor:${cursor}`,
			"outline:var(--tui-focus-outline)"
		].join(";");
	}
	setState(name, value) {
		if (this.state[name] === value) return;
		this.state[name] = value;
		this.updateToggleStyle();
	}
	updateToggleStyle() {
		this.toggleElement?.setAttribute("aria-checked", String(this.checked));
		this.toggleElement?.setAttribute("style", this.toggleStyle);
		this.blocksElement.textContent = this.blocks;
	}
	setToggleAttribute(name, value) {
		if (value === null) this.toggleElement.removeAttribute(name);
		else this.toggleElement.setAttribute(name, value);
	}
	toggle() {
		if (this.hasAttribute("disabled")) return;
		this.toggleAttribute("checked");
		this.updateToggleStyle();
		this.dispatchEvent(new Event("input", { bubbles: true }));
		this.dispatchEvent(new Event("change", { bubbles: true }));
	}
	bindToggleEvents() {
		this.toggleElement.addEventListener("click", () => this.toggle());
		this.toggleElement.addEventListener("mouseenter", () => this.setState("hover", true));
		this.toggleElement.addEventListener("mouseleave", () => {
			this.setState("hover", false);
			this.setState("active", false);
		});
		this.toggleElement.addEventListener("focus", () => this.setState("focus", true));
		this.toggleElement.addEventListener("blur", () => {
			this.setState("focus", false);
			this.setState("active", false);
		});
		this.toggleElement.addEventListener("pointerdown", () => this.setState("active", true));
		this.toggleElement.addEventListener("pointerup", () => this.setState("active", false));
		this.toggleElement.addEventListener("pointercancel", () => this.setState("active", false));
		this.toggleElement.addEventListener("keydown", (event) => {
			if (event.key === " " || event.key === "Enter") this.setState("active", true);
		});
		this.toggleElement.addEventListener("keyup", () => this.setState("active", false));
	}
	mount() {
		const authoredNodes = [...this.childNodes];
		this.state.active = false;
		this.state.focus = false;
		this.state.hover = false;
		this.innerHTML = `
			<button type="button" role="switch">
				<span data-tui-toggle-blocks aria-hidden="true"></span> <span data-tui-toggle-content></span>
			</button>
		`;
		this.toggleElement = this.querySelector("button");
		this.blocksElement = this.querySelector("[data-tui-toggle-blocks]");
		this.contentElement = this.querySelector("[data-tui-toggle-content]");
		this.contentElement.append(...authoredNodes);
		this.bindToggleEvents();
	}
	updateToggle() {
		this.toggleElement.disabled = this.hasAttribute("disabled");
		this.setToggleAttribute("name", this.getAttribute("name"));
		this.setToggleAttribute("value", this.getAttribute("value"));
		this.setToggleAttribute("aria-label", this.getAttribute("aria-label"));
		this.updateToggleStyle();
	}
	render() {
		if (!this.toggleElement) this.mount();
		this.updateToggle();
	}
};
customElements.define("tui-toggle", TuiToggle);
//#endregion
//#region ../../teract/src/tui-input.js
var types = /* @__PURE__ */ new Set([
	"date",
	"datetime-local",
	"email",
	"number",
	"password",
	"search",
	"tel",
	"text",
	"time",
	"url"
]);
var TuiInput = class extends TuiElement {
	state = {
		focus: false,
		hover: false
	};
	static observedAttributes = [
		"aria-label",
		"aria-labelledby",
		"autocomplete",
		"block",
		"disabled",
		"inputmode",
		"list",
		"max",
		"min",
		"name",
		"placeholder",
		"readonly",
		"required",
		"size",
		"step",
		"type",
		"value"
	];
	attributeChangedCallback(name, oldValue, newValue) {
		if (name === "value" && this.inputElement && oldValue !== newValue) {
			this.inputElement.value = newValue ?? "";
			return;
		}
		super.attributeChangedCallback();
	}
	get type() {
		const type = this.getAttribute("type") ?? "text";
		return types.has(type) ? type : "text";
	}
	get value() {
		return this.inputElement?.value ?? this.getAttribute("value") ?? "";
	}
	set value(value) {
		this.setAttribute("value", value ?? "");
	}
	get active() {
		return !this.hasAttribute("disabled") && (this.state.focus || this.state.hover);
	}
	get color() {
		return this.hasAttribute("disabled") ? "var(--tui-disabled-color)" : this.active ? "var(--tui-focus-color)" : "var(--tui-color)";
	}
	get background() {
		return this.active ? "var(--tui-focus-background)" : "var(--tui-background-transparent)";
	}
	get wrapperStyle() {
		return [
			...this.hasAttribute("block") ? [
				"display:flex",
				"width:100%",
				"min-width:0"
			] : [],
			`color:${this.color}`,
			`background:${this.background}`
		].join(";");
	}
	get inputStyle() {
		return [
			"all:var(--tui-reset-all)",
			"font-family:var(--tui-font-family)",
			`color:${this.color}`,
			"background:var(--tui-background-transparent)",
			"outline:var(--tui-focus-outline)",
			...this.hasAttribute("block") ? [
				"flex:1 1 auto",
				"width:100%",
				"min-width:0"
			] : []
		].join(";");
	}
	optionalAttribute(name) {
		const value = this.getAttribute(name);
		return value === null ? "" : ` ${name}="${this.escape(value)}"`;
	}
	booleanAttribute(name) {
		return this.hasAttribute(name) ? ` ${name}` : "";
	}
	setState(name, value) {
		if (this.state[name] === value) return;
		this.state[name] = value;
		this.updateStyle();
	}
	updateStyle() {
		this.wrapperElement?.setAttribute("style", this.wrapperStyle);
		this.inputElement?.setAttribute("style", this.inputStyle);
	}
	bindEvents() {
		this.wrapperElement.addEventListener("mouseenter", () => this.setState("hover", true));
		this.wrapperElement.addEventListener("mouseleave", () => this.setState("hover", false));
		this.inputElement.addEventListener("focus", () => this.setState("focus", true));
		this.inputElement.addEventListener("blur", () => this.setState("focus", false));
	}
	focus(options) {
		this.inputElement?.focus(options);
	}
	select() {
		this.inputElement?.select();
	}
	render() {
		this.style.display = this.hasAttribute("block") ? "block" : "inline";
		this.style.minWidth = this.hasAttribute("block") ? "0" : "";
		this.state.focus = false;
		this.state.hover = false;
		const value = this.getAttribute("value") ?? "";
		this.innerHTML = `
			<span data-tui-input style="${this.wrapperStyle}">
				<span aria-hidden="true">[</span><input type="${this.type}" value="${this.escape(value)}" style="${this.inputStyle}"${this.optionalAttribute("aria-label")}${this.optionalAttribute("aria-labelledby")}${this.optionalAttribute("autocomplete")}${this.optionalAttribute("inputmode")}${this.optionalAttribute("list")}${this.optionalAttribute("max")}${this.optionalAttribute("min")}${this.optionalAttribute("name")}${this.optionalAttribute("placeholder")}${this.optionalAttribute("size")}${this.optionalAttribute("step")}${this.booleanAttribute("disabled")}${this.booleanAttribute("readonly")}${this.booleanAttribute("required")} /><span aria-hidden="true">]</span>
			</span>
		`;
		this.wrapperElement = this.querySelector("[data-tui-input]");
		this.inputElement = this.querySelector("input");
		this.bindEvents();
	}
};
customElements.define("tui-input", TuiInput);
//#endregion
//#region ../../teract/src/tui-textarea.js
var TuiTextarea = class extends TuiElement {
	state = {
		focus: false,
		hover: false
	};
	static observedAttributes = [
		"aria-label",
		"aria-labelledby",
		"block",
		"cols",
		"disabled",
		"name",
		"placeholder",
		"readonly",
		"required",
		"rows",
		"value",
		"wrap"
	];
	attributeChangedCallback(name, oldValue, newValue) {
		if (name === "value" && this.textareaElement && oldValue !== newValue) {
			this.textareaElement.value = newValue ?? "";
			return;
		}
		super.attributeChangedCallback();
	}
	get value() {
		return this.textareaElement?.value ?? this.getAttribute("value") ?? "";
	}
	set value(value) {
		this.setAttribute("value", value ?? "");
	}
	get active() {
		return !this.hasAttribute("disabled") && (this.state.focus || this.state.hover);
	}
	get color() {
		return this.hasAttribute("disabled") ? "var(--tui-disabled-color)" : this.active ? "var(--tui-focus-color)" : "var(--tui-color)";
	}
	get background() {
		return this.active ? "var(--tui-focus-background)" : "var(--tui-background-transparent)";
	}
	get wrapperStyle() {
		return [
			"display:inline-flex",
			"align-items:flex-start",
			...this.hasAttribute("block") ? ["width:100%", "min-width:0"] : [],
			`color:${this.color}`,
			`background:${this.background}`
		].join(";");
	}
	get textareaStyle() {
		return [
			"all:var(--tui-reset-all)",
			"font-family:var(--tui-font-family)",
			`color:${this.color}`,
			"background:var(--tui-background-transparent)",
			"outline:var(--tui-focus-outline)",
			...this.hasAttribute("block") ? [
				"flex:1 1 auto",
				"width:100%",
				"min-width:0"
			] : []
		].join(";");
	}
	optionalAttribute(name) {
		const value = this.getAttribute(name);
		return value === null ? "" : ` ${name}="${this.escape(value)}"`;
	}
	booleanAttribute(name) {
		return this.hasAttribute(name) ? ` ${name}` : "";
	}
	setState(name, value) {
		if (this.state[name] === value) return;
		this.state[name] = value;
		this.updateStyle();
	}
	updateStyle() {
		this.wrapperElement?.setAttribute("style", this.wrapperStyle);
		this.textareaElement?.setAttribute("style", this.textareaStyle);
	}
	bindEvents() {
		this.wrapperElement.addEventListener("mouseenter", () => this.setState("hover", true));
		this.wrapperElement.addEventListener("mouseleave", () => this.setState("hover", false));
		this.textareaElement.addEventListener("focus", () => this.setState("focus", true));
		this.textareaElement.addEventListener("blur", () => this.setState("focus", false));
	}
	focus(options) {
		this.textareaElement?.focus(options);
	}
	select() {
		this.textareaElement?.select();
	}
	render() {
		this.style.display = this.hasAttribute("block") ? "block" : "inline";
		this.style.minWidth = this.hasAttribute("block") ? "0" : "";
		this.state.focus = false;
		this.state.hover = false;
		const value = this.getAttribute("value") ?? "";
		this.innerHTML = `
			<span data-tui-textarea style="${this.wrapperStyle}">
				<span aria-hidden="true">[</span><textarea style="${this.textareaStyle}"${this.optionalAttribute("aria-label")}${this.optionalAttribute("aria-labelledby")}${this.optionalAttribute("cols")}${this.optionalAttribute("name")}${this.optionalAttribute("placeholder")}${this.optionalAttribute("rows")}${this.optionalAttribute("wrap")}${this.booleanAttribute("disabled")}${this.booleanAttribute("readonly")}${this.booleanAttribute("required")}>${this.escape(value)}</textarea><span aria-hidden="true">]</span>
			</span>
		`;
		this.wrapperElement = this.querySelector("[data-tui-textarea]");
		this.textareaElement = this.querySelector("textarea");
		this.bindEvents();
	}
};
customElements.define("tui-textarea", TuiTextarea);
//#endregion
//#region ../../teract/src/tui-select.js
var TuiSelect = class extends TuiElement {
	optionObserver;
	state = {
		focus: false,
		hover: false
	};
	static observedAttributes = [
		"aria-label",
		"aria-labelledby",
		"disabled",
		"name",
		"required",
		"value"
	];
	attributeChangedCallback(name, oldValue, newValue) {
		if (name === "value" && this.selectElement && oldValue !== newValue) {
			this.selectElement.value = newValue ?? "";
			return;
		}
		super.attributeChangedCallback();
	}
	connectedCallback() {
		super.connectedCallback();
	}
	disconnectedCallback() {
		this.optionObserver?.disconnect();
	}
	get configuredValue() {
		return this.getAttribute("value") ?? [...this.querySelectorAll("option")].find((option) => option.selected)?.value ?? this.querySelector("option")?.value ?? "";
	}
	get value() {
		return this.selectElement?.value ?? this.configuredValue;
	}
	set value(value) {
		this.setAttribute("value", value ?? "");
	}
	get active() {
		return !this.hasAttribute("disabled") && (this.state.focus || this.state.hover);
	}
	get color() {
		return this.hasAttribute("disabled") ? "var(--tui-disabled-color)" : this.active ? "var(--tui-focus-color)" : "var(--tui-color)";
	}
	get background() {
		return this.active ? "var(--tui-focus-background)" : "var(--tui-background-transparent)";
	}
	get cursor() {
		return this.hasAttribute("disabled") ? "var(--tui-disabled-cursor)" : "var(--tui-action-cursor)";
	}
	get wrapperStyle() {
		return [
			`color:${this.color}`,
			`background:${this.background}`,
			`cursor:${this.cursor}`
		].join(";");
	}
	get selectStyle() {
		return [
			"all:var(--tui-reset-all)",
			"font-family:var(--tui-font-family)",
			`color:${this.color}`,
			"background:var(--tui-background-transparent)",
			`cursor:${this.cursor}`,
			"outline:var(--tui-focus-outline)"
		].join(";");
	}
	optionalAttribute(name) {
		const value = this.getAttribute(name);
		return value === null ? "" : ` ${name}="${this.escape(value)}"`;
	}
	booleanAttribute(name) {
		return this.hasAttribute(name) ? ` ${name}` : "";
	}
	setState(name, value) {
		if (this.state[name] === value) return;
		this.state[name] = value;
		this.updateStyle();
	}
	updateStyle() {
		this.wrapperElement?.setAttribute("style", this.wrapperStyle);
		this.selectElement?.setAttribute("style", this.selectStyle);
	}
	bindEvents() {
		this.wrapperElement.addEventListener("mouseenter", () => this.setState("hover", true));
		this.wrapperElement.addEventListener("mouseleave", () => this.setState("hover", false));
		this.selectElement.addEventListener("focus", () => this.setState("focus", true));
		this.selectElement.addEventListener("blur", () => this.setState("focus", false));
	}
	mount() {
		const authoredNodes = [...this.childNodes];
		this.innerHTML = `
			<span data-tui-select>
				<span aria-hidden="true">[</span><select></select><span aria-hidden="true">▼]</span>
			</span>
		`;
		this.wrapperElement = this.querySelector("[data-tui-select]");
		this.selectElement = this.querySelector("select");
		this.selectElement.append(...authoredNodes);
		this.bindEvents();
		this.optionObserver = new MutationObserver(() => {
			const configured = this.getAttribute("value");
			if (configured !== null) this.selectElement.value = configured;
		});
		this.optionObserver.observe(this.selectElement, {
			childList: true,
			subtree: true
		});
	}
	setOptionalAttribute(name) {
		const value = this.getAttribute(name);
		if (value === null) this.selectElement.removeAttribute(name);
		else this.selectElement.setAttribute(name, value);
	}
	updateSelect() {
		for (const name of [
			"aria-label",
			"aria-labelledby",
			"name"
		]) this.setOptionalAttribute(name);
		this.selectElement.disabled = this.hasAttribute("disabled");
		this.selectElement.required = this.hasAttribute("required");
		this.wrapperElement.setAttribute("style", this.wrapperStyle);
		this.selectElement.setAttribute("style", this.selectStyle);
		this.selectElement.value = this.configuredValue;
	}
	focus(options) {
		this.selectElement?.focus(options);
	}
	render() {
		if (!this.selectElement) {
			this.state.focus = false;
			this.state.hover = false;
			this.mount();
		}
		this.updateSelect();
	}
};
customElements.define("tui-select", TuiSelect);
//#endregion
//#region ../../teract/src/tui-progress.js
var TuiProgress = class extends TuiElement {
	static observedAttributes = [
		"aria-label",
		"columns",
		"max",
		"value"
	];
	get value() {
		const value = Number(this.getAttribute("value"));
		return Number.isFinite(value) ? value : 0;
	}
	get max() {
		const max = Number(this.getAttribute("max"));
		return Number.isFinite(max) && max > 0 ? max : 100;
	}
	get columns() {
		const columns = Number.parseInt(this.getAttribute("columns"), 10);
		return Number.isFinite(columns) && columns > 0 ? columns : 20;
	}
	render() {
		const ratio = Math.max(0, Math.min(1, this.value / this.max));
		const filled = Math.round(ratio * this.columns);
		const percentage = Math.round(ratio * 100);
		const label = this.getAttribute("aria-label") || "Progress";
		this.innerHTML = `
			<span role="progressbar" aria-label="${this.escape(label)}" aria-valuemin="0" aria-valuemax="${this.max}" aria-valuenow="${this.value}">
				<span aria-hidden="true">[${"█".repeat(filled)}${"░".repeat(this.columns - filled)}] ${percentage}%</span>
			</span>
		`;
	}
};
customElements.define("tui-progress", TuiProgress);
//#endregion
//#region ../../teract/src/tui-radio-button.js
var TuiRadioButton = class extends TuiElement {};
customElements.define("tui-radio-button", TuiRadioButton);
//#endregion
//#region ../../teract/src/tui-radio-buttonset.js
var TuiRadioButtonset = class extends TuiElement {
	state = {
		active: "",
		focus: "",
		hover: ""
	};
	static observedAttributes = [
		"aria-label",
		"disabled",
		"inverted",
		"name",
		"value"
	];
	connectedCallback() {
		super.connectedCallback();
	}
	cacheOptions() {
		if (this.options !== void 0) return;
		this.options = [...this.querySelectorAll("tui-radio-button")].map((option) => ({
			disabled: option.hasAttribute("disabled"),
			label: option.textContent.trim(),
			value: option.getAttribute("value") ?? option.textContent.trim(),
			checked: option.hasAttribute("checked")
		}));
	}
	get value() {
		const value = this.getAttribute("value");
		const checked = this.options?.find((option) => option.checked);
		return value ?? checked?.value ?? "";
	}
	get enabledOptions() {
		return this.options.filter((option) => !option.disabled);
	}
	optionChecked(option) {
		return this.value === option.value;
	}
	optionDisabled(option) {
		return this.hasAttribute("disabled") || option.disabled;
	}
	optionActive(option) {
		return !this.optionDisabled(option) && (this.state.hover === option.value || this.state.focus === option.value || this.state.active === option.value);
	}
	optionColor(option) {
		if (this.optionDisabled(option)) return "var(--tui-disabled-color)";
		if (this.hasAttribute("inverted")) return this.optionActive(option) || this.optionChecked(option) ? "var(--tui-color)" : "var(--tui-background)";
		if (this.optionActive(option) || this.optionChecked(option)) return "var(--tui-focus-color)";
		return "var(--tui-color)";
	}
	optionBackground(option) {
		if (this.optionActive(option) || this.optionChecked(option)) return this.hasAttribute("inverted") ? "var(--tui-background)" : "var(--tui-focus-background)";
		return "var(--tui-background-transparent)";
	}
	optionCursor(option) {
		return this.optionDisabled(option) ? "var(--tui-disabled-cursor)" : "var(--tui-action-cursor)";
	}
	optionTextDecoration(option) {
		return this.state.active === option.value ? "var(--tui-active-text-decoration)" : "var(--tui-text-decoration)";
	}
	optionStyle(option) {
		return [
			"all:var(--tui-reset-all)",
			"font-family:var(--tui-font-family)",
			`color:${this.optionColor(option)}`,
			`background:${this.optionBackground(option)}`,
			`text-decoration:${this.optionTextDecoration(option)}`,
			`cursor:${this.optionCursor(option)}`,
			"outline:var(--tui-focus-outline)"
		].join(";");
	}
	optionTabIndex(option) {
		if (this.optionDisabled(option)) return "-1";
		if (this.value === "") return this.enabledOptions[0]?.value === option.value ? "0" : "-1";
		return this.optionChecked(option) ? "0" : "-1";
	}
	setState(name, value) {
		if (this.state[name] === value) return;
		this.state[name] = value;
		this.updateOptions();
	}
	updateOptions() {
		for (const button of this.querySelectorAll("button")) {
			const option = this.options.find((item) => item.value === button.getAttribute("value"));
			button.setAttribute("aria-checked", String(this.optionChecked(option)));
			button.setAttribute("style", this.optionStyle(option));
			button.setAttribute("tabindex", this.optionTabIndex(option));
		}
		this.inputElement?.setAttribute("value", this.value);
	}
	select(value) {
		const option = this.options.find((item) => item.value === value);
		if (option === void 0 || this.optionDisabled(option) || this.value === option.value) return;
		this.setAttribute("value", option.value);
		this.updateOptions();
		this.dispatchEvent(new Event("input", { bubbles: true }));
		this.dispatchEvent(new Event("change", { bubbles: true }));
	}
	focusNextOption(value, direction) {
		const group = this.enabledOptions;
		if (group.length === 0) return;
		const index = group.findIndex((option) => option.value === value);
		const next = group.at((index + direction + group.length) % group.length);
		this.select(next.value);
		this.querySelector(`button[value="${CSS.escape(next.value)}"]`)?.focus();
	}
	bindOptionEvents() {
		for (const button of this.querySelectorAll("button")) {
			const value = button.getAttribute("value");
			button.addEventListener("click", () => this.select(value));
			button.addEventListener("mouseenter", () => this.setState("hover", value));
			button.addEventListener("mouseleave", () => {
				this.setState("hover", "");
				this.setState("active", "");
			});
			button.addEventListener("focus", () => this.setState("focus", value));
			button.addEventListener("blur", () => {
				this.setState("focus", "");
				this.setState("active", "");
			});
			button.addEventListener("pointerdown", () => this.setState("active", value));
			button.addEventListener("pointerup", () => this.setState("active", ""));
			button.addEventListener("pointercancel", () => this.setState("active", ""));
			button.addEventListener("keydown", (event) => {
				if (event.key === " " || event.key === "Enter") this.setState("active", value);
				if (event.key === "ArrowRight" || event.key === "ArrowDown") {
					event.preventDefault();
					this.focusNextOption(value, 1);
				}
				if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
					event.preventDefault();
					this.focusNextOption(value, -1);
				}
			});
			button.addEventListener("keyup", () => this.setState("active", ""));
		}
	}
	renderOption(option) {
		const disabled = this.optionDisabled(option) ? " disabled" : "";
		return `<button type="button" role="radio" aria-checked="${this.optionChecked(option)}" value="${this.escape(option.value)}" tabindex="${this.optionTabIndex(option)}" style="${this.optionStyle(option)}"${disabled}>${this.escape(option.label)}</button>`;
	}
	renderOptions() {
		return this.options.map((option) => this.renderOption(option)).join("<span aria-hidden=\"true\">&nbsp;|&nbsp;</span>");
	}
	render() {
		this.cacheOptions();
		this.state.active = "";
		this.state.focus = "";
		this.state.hover = "";
		const name = this.getAttribute("name");
		const label = this.getAttribute("aria-label");
		const labelAttribute = label === null ? "" : ` aria-label="${this.escape(label)}"`;
		const disabled = this.hasAttribute("disabled") ? " disabled" : "";
		const input = name === null ? "" : `<input type="hidden" name="${this.escape(name)}" value="${this.escape(this.value)}"${disabled} />`;
		this.innerHTML = `
			<span role="radiogroup"${labelAttribute}>
				<span aria-hidden="true">[</span>${this.renderOptions()}<span aria-hidden="true">]</span>
			</span>
			${input}
		`;
		this.inputElement = this.querySelector("input");
		this.bindOptionEvents();
	}
};
customElements.define("tui-radio-buttonset", TuiRadioButtonset);
//#endregion
//#region ../../teract/src/tui-sparkline.js
var blocks = "▁▂▃▄▅▆▇█";
var variants$1 = /* @__PURE__ */ new Set([
	"success",
	"warning",
	"error"
]);
function finiteNumber$1(value) {
	if (value === null || value === void 0 || value === "") return;
	const number = Number(value);
	return Number.isFinite(number) ? number : void 0;
}
var TuiSparkline = class extends TuiElement {
	#values = [];
	static observedAttributes = [
		"above-variant",
		"aria-label",
		"below-variant",
		"columns",
		"max",
		"min",
		"threshold",
		"variant"
	];
	get values() {
		return this.#values;
	}
	set values(values) {
		this.#values = Array.isArray(values) ? values : [];
		if (this.isConnected) this.render();
	}
	get columns() {
		const columns = Number.parseInt(this.getAttribute("columns"), 10);
		return Number.isFinite(columns) && columns > 0 ? columns : 40;
	}
	attributeNumber(name) {
		const attribute = this.getAttribute(name);
		if (attribute === null || attribute === "") return;
		const value = Number(attribute);
		return Number.isFinite(value) ? value : void 0;
	}
	variant(name) {
		const variant = this.getAttribute(name);
		return variants$1.has(variant) ? variant : void 0;
	}
	sampledValues() {
		if (this.#values.length === 0 || this.#values.length === this.columns) return this.#values;
		if (this.#values.length < this.columns) {
			if (this.#values.length === 1) return Array(this.columns).fill(this.#values[0]);
			return Array.from({ length: this.columns }, (_, column) => {
				const position = column * (this.#values.length - 1) / (this.columns - 1);
				const lowerIndex = Math.floor(position);
				const upperIndex = Math.ceil(position);
				const lower = finiteNumber$1(this.#values[lowerIndex]);
				const upper = finiteNumber$1(this.#values[upperIndex]);
				if (!Number.isFinite(lower) || !Number.isFinite(upper)) return;
				return lower + (upper - lower) * (position - lowerIndex);
			});
		}
		return Array.from({ length: this.columns }, (_, column) => {
			const start = Math.floor(column * this.#values.length / this.columns);
			const end = Math.max(start + 1, Math.floor((column + 1) * this.#values.length / this.columns));
			const values = this.#values.slice(start, end).map(finiteNumber$1).filter(Number.isFinite);
			if (values.length === 0) return;
			return values.reduce((sum, value) => sum + value, 0) / values.length;
		});
	}
	render() {
		const values = this.sampledValues();
		const finiteValues = values.map(finiteNumber$1).filter(Number.isFinite);
		const minimum = this.attributeNumber("min") ?? Math.min(...finiteValues);
		const range = (this.attributeNumber("max") ?? Math.max(...finiteValues)) - minimum;
		const threshold = this.attributeNumber("threshold");
		const aboveVariant = this.variant("above-variant");
		const belowVariant = this.variant("below-variant");
		const defaultVariant = this.variant("variant");
		const label = this.getAttribute("aria-label") ?? "Trend";
		const points = values.map((value) => {
			const number = finiteNumber$1(value);
			if (!Number.isFinite(number)) return {
				glyph: " ",
				variant: void 0
			};
			return {
				glyph: !Number.isFinite(range) || range === 0 ? blocks[3] : blocks[Math.round(Math.max(0, Math.min(1, (number - minimum) / range)) * 7)],
				variant: threshold === void 0 ? defaultVariant : number > threshold ? aboveVariant : number < threshold ? belowVariant : defaultVariant
			};
		});
		const segments = [];
		for (const point of points) {
			const last = segments.at(-1);
			if (last && last.variant === point.variant) last.glyphs += point.glyph;
			else segments.push({
				glyphs: point.glyph,
				variant: point.variant
			});
		}
		const graph = segments.map(({ glyphs, variant }) => {
			return `<span${variant ? ` style="color:var(--tui-${variant}-color)"` : ""}>${glyphs}</span>`;
		}).join("");
		this.innerHTML = `<span role="img" aria-label="${this.escape(label)}"><span aria-hidden="true">${graph}</span></span>`;
	}
};
customElements.define("tui-sparkline", TuiSparkline);
//#endregion
//#region ../../teract/src/tui-chart.js
var variants = /* @__PURE__ */ new Set([
	"success",
	"warning",
	"error"
]);
var brailleBitByPosition = [[
	1,
	2,
	4,
	64
], [
	8,
	16,
	32,
	128
]];
function finiteNumber(value) {
	if (value === null || value === void 0 || value === "") return;
	const number = Number(value);
	return Number.isFinite(number) ? number : void 0;
}
var TuiChart = class extends TuiElement {
	#values = [];
	#responsiveColumns = 40;
	#resizeObserver;
	static observedAttributes = [
		"above-variant",
		"aria-label",
		"below-variant",
		"columns",
		"height",
		"max",
		"min",
		"threshold"
	];
	get values() {
		return this.#values;
	}
	set values(values) {
		this.#values = Array.isArray(values) ? values : [];
		if (this.isConnected) this.render();
	}
	get columns() {
		const columns = Number.parseInt(this.getAttribute("columns"), 10);
		return Number.isFinite(columns) && columns > 0 ? columns : this.#responsiveColumns;
	}
	get height() {
		const height = Number.parseInt(this.getAttribute("height"), 10);
		return Number.isFinite(height) && height > 0 ? height : 1;
	}
	attributeNumber(name) {
		const attribute = this.getAttribute(name);
		if (attribute === null || attribute === "") return;
		const value = Number(attribute);
		return Number.isFinite(value) ? value : void 0;
	}
	variant(name) {
		const variant = this.getAttribute(name);
		return variants.has(variant) ? variant : void 0;
	}
	connectedCallback() {
		this.style.display = "block";
		this.style.minWidth = "0";
		this.style.overflow = "hidden";
		this.style.whiteSpace = "nowrap";
		super.connectedCallback();
		if (typeof ResizeObserver !== "undefined") {
			this.#resizeObserver = new ResizeObserver(() => this.#syncResponsiveColumns());
			this.#resizeObserver.observe(this);
			queueMicrotask(() => this.#syncResponsiveColumns());
		}
	}
	disconnectedCallback() {
		this.#resizeObserver?.disconnect();
	}
	#syncResponsiveColumns() {
		const width = this.getBoundingClientRect().width;
		if (!(width > 0)) return;
		const context = document.createElement("canvas").getContext("2d");
		if (!context) return;
		const computed = getComputedStyle(this);
		context.font = computed.font || `${computed.fontSize} ${computed.fontFamily}`;
		const characterWidth = context.measureText("⣿").width;
		if (!(characterWidth > 0)) return;
		const columns = Math.max(1, Math.floor(width / characterWidth));
		if (columns === this.#responsiveColumns) return;
		this.#responsiveColumns = columns;
		if (!this.hasAttribute("columns")) this.render();
	}
	sampledValues() {
		const sampleCount = this.columns * 2;
		if (this.#values.length === 0 || this.#values.length === sampleCount) return this.#values;
		if (this.#values.length < sampleCount) {
			if (this.#values.length === 1) return Array(sampleCount).fill(this.#values[0]);
			return Array.from({ length: sampleCount }, (_, column) => {
				const position = column * (this.#values.length - 1) / (sampleCount - 1);
				const lowerIndex = Math.floor(position);
				const upperIndex = Math.ceil(position);
				const lower = finiteNumber(this.#values[lowerIndex]);
				const upper = finiteNumber(this.#values[upperIndex]);
				if (!Number.isFinite(lower) || !Number.isFinite(upper)) return;
				return lower + (upper - lower) * (position - lowerIndex);
			});
		}
		return Array.from({ length: this.columns }, (_, cell) => {
			const start = Math.floor(cell * this.#values.length / this.columns);
			const end = Math.max(start + 1, Math.floor((cell + 1) * this.#values.length / this.columns));
			const values = this.#values.slice(start, end).map((value, index) => ({
				index,
				value: finiteNumber(value)
			})).filter(({ value }) => Number.isFinite(value));
			if (values.length === 0) return [void 0, void 0];
			let minimum = values[0];
			let maximum = values[0];
			for (const point of values.slice(1)) {
				if (point.value < minimum.value) minimum = point;
				if (point.value > maximum.value) maximum = point;
			}
			return minimum.index <= maximum.index ? [minimum.value, maximum.value] : [maximum.value, minimum.value];
		}).flat();
	}
	pixelFor(value, minimum, maximum) {
		const number = finiteNumber(value);
		if (!Number.isFinite(number)) return;
		const pixelHeight = this.height * 4;
		const range = maximum - minimum;
		if (!Number.isFinite(range) || range === 0) return Math.floor((pixelHeight - 1) / 2);
		const ratio = Math.max(0, Math.min(1, (maximum - number) / range));
		return Math.min(pixelHeight - 1, Math.floor(ratio * pixelHeight));
	}
	drawLine(pixels, start, end) {
		let x = start.x;
		let y = start.y;
		const horizontal = Math.abs(end.x - start.x);
		const vertical = -Math.abs(end.y - start.y);
		const stepX = start.x < end.x ? 1 : -1;
		const stepY = start.y < end.y ? 1 : -1;
		let error = horizontal + vertical;
		while (true) {
			pixels[y][x] = 1;
			if (x === end.x && y === end.y) break;
			const doubledError = error * 2;
			if (doubledError >= vertical) {
				error += vertical;
				x += stepX;
			}
			if (doubledError <= horizontal) {
				error += horizontal;
				y += stepY;
			}
		}
	}
	rowsFor(values, minimum, maximum) {
		const pixels = Array.from({ length: this.height * 4 }, () => new Uint8Array(values.length));
		let previous;
		for (const [x, value] of values.entries()) {
			const y = this.pixelFor(value, minimum, maximum);
			if (y === void 0) {
				previous = void 0;
				continue;
			}
			const point = {
				x,
				y
			};
			if (previous) this.drawLine(pixels, previous, point);
			else pixels[y][x] = 1;
			previous = point;
		}
		const rows = Array.from({ length: this.height }, () => []);
		for (let cell = 0; cell < this.columns; cell += 1) for (let line = 0; line < this.height; line += 1) {
			let mask = 0;
			for (let column = 0; column < 2; column += 1) {
				const x = cell * 2 + column;
				for (let row = 0; row < 4; row += 1) if (pixels[line * 4 + row][x]) mask |= brailleBitByPosition[column][row];
			}
			rows[line].push(String.fromCodePoint(10240 + mask));
		}
		return rows.map((row) => row.join(""));
	}
	thresholdScale(minimum, maximum, threshold) {
		if (threshold === void 0 || !Number.isFinite(minimum) || !Number.isFinite(maximum) || maximum <= minimum) return {
			minimum,
			maximum,
			thresholdRow: void 0
		};
		if (threshold <= minimum) return {
			minimum,
			maximum,
			thresholdRow: this.height
		};
		if (threshold >= maximum) return {
			minimum,
			maximum,
			thresholdRow: 0
		};
		if (this.height < 2) return {
			minimum,
			maximum,
			thresholdRow: void 0
		};
		const aboveRange = maximum - threshold;
		const belowRange = threshold - minimum;
		let best;
		for (let aboveRows = 1; aboveRows < this.height; aboveRows += 1) {
			const belowRows = this.height - aboveRows;
			const rangePerRow = Math.max(aboveRange / aboveRows, belowRange / belowRows);
			if (!best || rangePerRow < best.rangePerRow) best = {
				aboveRows,
				belowRows,
				rangePerRow
			};
		}
		return {
			minimum: threshold - best.rangePerRow * best.belowRows,
			maximum: threshold + best.rangePerRow * best.aboveRows,
			thresholdRow: best.aboveRows
		};
	}
	rowVariant(row, thresholdRow) {
		if (thresholdRow === void 0) return;
		return row < thresholdRow ? this.variant("above-variant") : this.variant("below-variant");
	}
	singleRowMarkup(row, values, threshold) {
		const segments = [];
		for (const [cell, glyph] of [...row].entries()) {
			const cellValues = values.slice(cell * 2, cell * 2 + 2).map(finiteNumber).filter(Number.isFinite);
			let variant;
			if (cellValues.length > 0 && cellValues.every((value) => value > threshold)) variant = this.variant("above-variant");
			else if (cellValues.length > 0 && cellValues.every((value) => value < threshold)) variant = this.variant("below-variant");
			const previous = segments.at(-1);
			if (previous && previous.variant === variant) previous.glyphs += glyph;
			else segments.push({
				glyphs: glyph,
				variant
			});
		}
		return segments.map(({ glyphs, variant }) => {
			return `<span${variant ? ` style="color:var(--tui-${variant}-color)"` : ""}>${glyphs}</span>`;
		}).join("");
	}
	render() {
		const values = this.sampledValues();
		const finiteValues = values.map(finiteNumber).filter(Number.isFinite);
		const minimum = this.attributeNumber("min") ?? Math.min(...finiteValues);
		const maximum = this.attributeNumber("max") ?? Math.max(...finiteValues);
		const threshold = this.attributeNumber("threshold");
		const scale = this.thresholdScale(minimum, maximum, threshold);
		const label = this.getAttribute("aria-label") ?? "Chart";
		const graph = this.rowsFor(values, scale.minimum, scale.maximum).map((row, index) => {
			if (this.height === 1 && threshold !== void 0 && scale.thresholdRow === void 0) return `<span data-tui-chart-row="${index}">${this.singleRowMarkup(row, values, threshold)}</span>`;
			const variant = this.rowVariant(index, scale.thresholdRow);
			return `<span data-tui-chart-row="${index}"${variant ? ` style="color:var(--tui-${variant}-color)"` : ""}>${row}</span>`;
		}).join("<br>");
		this.innerHTML = `<span role="img" aria-label="${this.escape(label)}"><span aria-hidden="true">${graph}</span></span>`;
	}
};
customElements.define("tui-chart", TuiChart);
//#endregion
//#region node_modules/@lit/reactive-element/css-tag.js
/**
* @license
* Copyright 2019 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var t$1 = globalThis;
var e$2 = t$1.ShadowRoot && (void 0 === t$1.ShadyCSS || t$1.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype;
var s$2 = Symbol();
var o$3 = /* @__PURE__ */ new WeakMap();
var n$2 = class {
	constructor(t, e, o) {
		if (this._$cssResult$ = !0, o !== s$2) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
		this.cssText = t, this.t = e;
	}
	get styleSheet() {
		let t = this.o;
		const s = this.t;
		if (e$2 && void 0 === t) {
			const e = void 0 !== s && 1 === s.length;
			e && (t = o$3.get(s)), void 0 === t && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), e && o$3.set(s, t));
		}
		return t;
	}
	toString() {
		return this.cssText;
	}
};
var r$2 = (t) => new n$2("string" == typeof t ? t : t + "", void 0, s$2);
var S$1 = (s, o) => {
	if (e$2) s.adoptedStyleSheets = o.map((t) => t instanceof CSSStyleSheet ? t : t.styleSheet);
	else for (const e of o) {
		const o = document.createElement("style"), n = t$1.litNonce;
		void 0 !== n && o.setAttribute("nonce", n), o.textContent = e.cssText, s.appendChild(o);
	}
};
var c$2 = e$2 ? (t) => t : (t) => t instanceof CSSStyleSheet ? ((t) => {
	let e = "";
	for (const s of t.cssRules) e += s.cssText;
	return r$2(e);
})(t) : t;
//#endregion
//#region node_modules/@lit/reactive-element/reactive-element.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var { is: i$2, defineProperty: e$1, getOwnPropertyDescriptor: h$1, getOwnPropertyNames: r$1, getOwnPropertySymbols: o$2, getPrototypeOf: n$1 } = Object, a$1 = globalThis, c$1 = a$1.trustedTypes, l$1 = c$1 ? c$1.emptyScript : "", p$1 = a$1.reactiveElementPolyfillSupport, d$1 = (t, s) => t, u$1 = {
	toAttribute(t, s) {
		switch (s) {
			case Boolean:
				t = t ? l$1 : null;
				break;
			case Object:
			case Array: t = null == t ? t : JSON.stringify(t);
		}
		return t;
	},
	fromAttribute(t, s) {
		let i = t;
		switch (s) {
			case Boolean:
				i = null !== t;
				break;
			case Number:
				i = null === t ? null : Number(t);
				break;
			case Object:
			case Array: try {
				i = JSON.parse(t);
			} catch (t) {
				i = null;
			}
		}
		return i;
	}
}, f$1 = (t, s) => !i$2(t, s), b$1 = {
	attribute: !0,
	type: String,
	converter: u$1,
	reflect: !1,
	useDefault: !1,
	hasChanged: f$1
};
Symbol.metadata ??= Symbol("metadata"), a$1.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
var y$1 = class extends HTMLElement {
	static addInitializer(t) {
		this._$Ei(), (this.l ??= []).push(t);
	}
	static get observedAttributes() {
		return this.finalize(), this._$Eh && [...this._$Eh.keys()];
	}
	static createProperty(t, s = b$1) {
		if (s.state && (s.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(t) && ((s = Object.create(s)).wrapped = !0), this.elementProperties.set(t, s), !s.noAccessor) {
			const i = Symbol(), h = this.getPropertyDescriptor(t, i, s);
			void 0 !== h && e$1(this.prototype, t, h);
		}
	}
	static getPropertyDescriptor(t, s, i) {
		const { get: e, set: r } = h$1(this.prototype, t) ?? {
			get() {
				return this[s];
			},
			set(t) {
				this[s] = t;
			}
		};
		return {
			get: e,
			set(s) {
				const h = e?.call(this);
				r?.call(this, s), this.requestUpdate(t, h, i);
			},
			configurable: !0,
			enumerable: !0
		};
	}
	static getPropertyOptions(t) {
		return this.elementProperties.get(t) ?? b$1;
	}
	static _$Ei() {
		if (this.hasOwnProperty(d$1("elementProperties"))) return;
		const t = n$1(this);
		t.finalize(), void 0 !== t.l && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
	}
	static finalize() {
		if (this.hasOwnProperty(d$1("finalized"))) return;
		if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(d$1("properties"))) {
			const t = this.properties, s = [...r$1(t), ...o$2(t)];
			for (const i of s) this.createProperty(i, t[i]);
		}
		const t = this[Symbol.metadata];
		if (null !== t) {
			const s = litPropertyMetadata.get(t);
			if (void 0 !== s) for (const [t, i] of s) this.elementProperties.set(t, i);
		}
		this._$Eh = /* @__PURE__ */ new Map();
		for (const [t, s] of this.elementProperties) {
			const i = this._$Eu(t, s);
			void 0 !== i && this._$Eh.set(i, t);
		}
		this.elementStyles = this.finalizeStyles(this.styles);
	}
	static finalizeStyles(s) {
		const i = [];
		if (Array.isArray(s)) {
			const e = new Set(s.flat(1 / 0).reverse());
			for (const s of e) i.unshift(c$2(s));
		} else void 0 !== s && i.push(c$2(s));
		return i;
	}
	static _$Eu(t, s) {
		const i = s.attribute;
		return !1 === i ? void 0 : "string" == typeof i ? i : "string" == typeof t ? t.toLowerCase() : void 0;
	}
	constructor() {
		super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
	}
	_$Ev() {
		this._$ES = new Promise((t) => this.enableUpdating = t), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((t) => t(this));
	}
	addController(t) {
		(this._$EO ??= /* @__PURE__ */ new Set()).add(t), void 0 !== this.renderRoot && this.isConnected && t.hostConnected?.();
	}
	removeController(t) {
		this._$EO?.delete(t);
	}
	_$E_() {
		const t = /* @__PURE__ */ new Map(), s = this.constructor.elementProperties;
		for (const i of s.keys()) this.hasOwnProperty(i) && (t.set(i, this[i]), delete this[i]);
		t.size > 0 && (this._$Ep = t);
	}
	createRenderRoot() {
		const t = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
		return S$1(t, this.constructor.elementStyles), t;
	}
	connectedCallback() {
		this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((t) => t.hostConnected?.());
	}
	enableUpdating(t) {}
	disconnectedCallback() {
		this._$EO?.forEach((t) => t.hostDisconnected?.());
	}
	attributeChangedCallback(t, s, i) {
		this._$AK(t, i);
	}
	_$ET(t, s) {
		const i = this.constructor.elementProperties.get(t), e = this.constructor._$Eu(t, i);
		if (void 0 !== e && !0 === i.reflect) {
			const h = (void 0 !== i.converter?.toAttribute ? i.converter : u$1).toAttribute(s, i.type);
			this._$Em = t, null == h ? this.removeAttribute(e) : this.setAttribute(e, h), this._$Em = null;
		}
	}
	_$AK(t, s) {
		const i = this.constructor, e = i._$Eh.get(t);
		if (void 0 !== e && this._$Em !== e) {
			const t = i.getPropertyOptions(e), h = "function" == typeof t.converter ? { fromAttribute: t.converter } : void 0 !== t.converter?.fromAttribute ? t.converter : u$1;
			this._$Em = e;
			const r = h.fromAttribute(s, t.type);
			this[e] = r ?? this._$Ej?.get(e) ?? r, this._$Em = null;
		}
	}
	requestUpdate(t, s, i, e = !1, h) {
		if (void 0 !== t) {
			const r = this.constructor;
			if (!1 === e && (h = this[t]), i ??= r.getPropertyOptions(t), !((i.hasChanged ?? f$1)(h, s) || i.useDefault && i.reflect && h === this._$Ej?.get(t) && !this.hasAttribute(r._$Eu(t, i)))) return;
			this.C(t, s, i);
		}
		!1 === this.isUpdatePending && (this._$ES = this._$EP());
	}
	C(t, s, { useDefault: i, reflect: e, wrapped: h }, r) {
		i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t) && (this._$Ej.set(t, r ?? s ?? this[t]), !0 !== h || void 0 !== r) || (this._$AL.has(t) || (this.hasUpdated || i || (s = void 0), this._$AL.set(t, s)), !0 === e && this._$Em !== t && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t));
	}
	async _$EP() {
		this.isUpdatePending = !0;
		try {
			await this._$ES;
		} catch (t) {
			Promise.reject(t);
		}
		const t = this.scheduleUpdate();
		return null != t && await t, !this.isUpdatePending;
	}
	scheduleUpdate() {
		return this.performUpdate();
	}
	performUpdate() {
		if (!this.isUpdatePending) return;
		if (!this.hasUpdated) {
			if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
				for (const [t, s] of this._$Ep) this[t] = s;
				this._$Ep = void 0;
			}
			const t = this.constructor.elementProperties;
			if (t.size > 0) for (const [s, i] of t) {
				const { wrapped: t } = i, e = this[s];
				!0 !== t || this._$AL.has(s) || void 0 === e || this.C(s, void 0, i, e);
			}
		}
		let t = !1;
		const s = this._$AL;
		try {
			t = this.shouldUpdate(s), t ? (this.willUpdate(s), this._$EO?.forEach((t) => t.hostUpdate?.()), this.update(s)) : this._$EM();
		} catch (s) {
			throw t = !1, this._$EM(), s;
		}
		t && this._$AE(s);
	}
	willUpdate(t) {}
	_$AE(t) {
		this._$EO?.forEach((t) => t.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(t)), this.updated(t);
	}
	_$EM() {
		this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
	}
	get updateComplete() {
		return this.getUpdateComplete();
	}
	getUpdateComplete() {
		return this._$ES;
	}
	shouldUpdate(t) {
		return !0;
	}
	update(t) {
		this._$Eq &&= this._$Eq.forEach((t) => this._$ET(t, this[t])), this._$EM();
	}
	updated(t) {}
	firstUpdated(t) {}
};
y$1.elementStyles = [], y$1.shadowRootOptions = { mode: "open" }, y$1[d$1("elementProperties")] = /* @__PURE__ */ new Map(), y$1[d$1("finalized")] = /* @__PURE__ */ new Map(), p$1?.({ ReactiveElement: y$1 }), (a$1.reactiveElementVersions ??= []).push("2.1.2");
//#endregion
//#region node_modules/lit-html/lit-html.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var t = globalThis;
var i$1 = (t) => t;
var s$1 = t.trustedTypes;
var e = s$1 ? s$1.createPolicy("lit-html", { createHTML: (t) => t }) : void 0;
var h = "$lit$";
var o$1 = `lit$${Math.random().toFixed(9).slice(2)}$`;
var n = "?" + o$1;
var r = `<${n}>`;
var l = document;
var c = () => l.createComment("");
var a = (t) => null === t || "object" != typeof t && "function" != typeof t;
var u = Array.isArray;
var d = (t) => u(t) || "function" == typeof t?.[Symbol.iterator];
var f = "[ 	\n\f\r]";
var v = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g;
var _ = /-->/g;
var m = />/g;
var p = RegExp(`>|${f}(?:([^\\s"'>=/]+)(${f}*=${f}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`, "g");
var g = /'/g;
var $ = /"/g;
var y = /^(?:script|style|textarea|title)$/i;
var x = (t) => (i, ...s) => ({
	_$litType$: t,
	strings: i,
	values: s
});
var b = x(1);
var E = Symbol.for("lit-noChange");
var A = Symbol.for("lit-nothing");
var C = /* @__PURE__ */ new WeakMap();
var P = l.createTreeWalker(l, 129);
function V(t, i) {
	if (!u(t) || !t.hasOwnProperty("raw")) throw Error("invalid template strings array");
	return void 0 !== e ? e.createHTML(i) : i;
}
var N = (t, i) => {
	const s = t.length - 1, e = [];
	let n, l = 2 === i ? "<svg>" : 3 === i ? "<math>" : "", c = v;
	for (let i = 0; i < s; i++) {
		const s = t[i];
		let a, u, d = -1, f = 0;
		for (; f < s.length && (c.lastIndex = f, u = c.exec(s), null !== u);) f = c.lastIndex, c === v ? "!--" === u[1] ? c = _ : void 0 !== u[1] ? c = m : void 0 !== u[2] ? (y.test(u[2]) && (n = RegExp("</" + u[2], "g")), c = p) : void 0 !== u[3] && (c = p) : c === p ? ">" === u[0] ? (c = n ?? v, d = -1) : void 0 === u[1] ? d = -2 : (d = c.lastIndex - u[2].length, a = u[1], c = void 0 === u[3] ? p : "\"" === u[3] ? $ : g) : c === $ || c === g ? c = p : c === _ || c === m ? c = v : (c = p, n = void 0);
		const x = c === p && t[i + 1].startsWith("/>") ? " " : "";
		l += c === v ? s + r : d >= 0 ? (e.push(a), s.slice(0, d) + h + s.slice(d) + o$1 + x) : s + o$1 + (-2 === d ? i : x);
	}
	return [V(t, l + (t[s] || "<?>") + (2 === i ? "</svg>" : 3 === i ? "</math>" : "")), e];
};
var S = class S {
	constructor({ strings: t, _$litType$: i }, e) {
		let r;
		this.parts = [];
		let l = 0, a = 0;
		const u = t.length - 1, d = this.parts, [f, v] = N(t, i);
		if (this.el = S.createElement(f, e), P.currentNode = this.el.content, 2 === i || 3 === i) {
			const t = this.el.content.firstChild;
			t.replaceWith(...t.childNodes);
		}
		for (; null !== (r = P.nextNode()) && d.length < u;) {
			if (1 === r.nodeType) {
				if (r.hasAttributes()) for (const t of r.getAttributeNames()) if (t.endsWith(h)) {
					const i = v[a++], s = r.getAttribute(t).split(o$1), e = /([.?@])?(.*)/.exec(i);
					d.push({
						type: 1,
						index: l,
						name: e[2],
						strings: s,
						ctor: "." === e[1] ? I : "?" === e[1] ? L : "@" === e[1] ? z : H
					}), r.removeAttribute(t);
				} else t.startsWith(o$1) && (d.push({
					type: 6,
					index: l
				}), r.removeAttribute(t));
				if (y.test(r.tagName)) {
					const t = r.textContent.split(o$1), i = t.length - 1;
					if (i > 0) {
						r.textContent = s$1 ? s$1.emptyScript : "";
						for (let s = 0; s < i; s++) r.append(t[s], c()), P.nextNode(), d.push({
							type: 2,
							index: ++l
						});
						r.append(t[i], c());
					}
				}
			} else if (8 === r.nodeType) if (r.data === n) d.push({
				type: 2,
				index: l
			});
			else {
				let t = -1;
				for (; -1 !== (t = r.data.indexOf(o$1, t + 1));) d.push({
					type: 7,
					index: l
				}), t += o$1.length - 1;
			}
			l++;
		}
	}
	static createElement(t, i) {
		const s = l.createElement("template");
		return s.innerHTML = t, s;
	}
};
function M(t, i, s = t, e) {
	if (i === E) return i;
	let h = void 0 !== e ? s._$Co?.[e] : s._$Cl;
	const o = a(i) ? void 0 : i._$litDirective$;
	return h?.constructor !== o && (h?._$AO?.(!1), void 0 === o ? h = void 0 : (h = new o(t), h._$AT(t, s, e)), void 0 !== e ? (s._$Co ??= [])[e] = h : s._$Cl = h), void 0 !== h && (i = M(t, h._$AS(t, i.values), h, e)), i;
}
var R = class {
	constructor(t, i) {
		this._$AV = [], this._$AN = void 0, this._$AD = t, this._$AM = i;
	}
	get parentNode() {
		return this._$AM.parentNode;
	}
	get _$AU() {
		return this._$AM._$AU;
	}
	u(t) {
		const { el: { content: i }, parts: s } = this._$AD, e = (t?.creationScope ?? l).importNode(i, !0);
		P.currentNode = e;
		let h = P.nextNode(), o = 0, n = 0, r = s[0];
		for (; void 0 !== r;) {
			if (o === r.index) {
				let i;
				2 === r.type ? i = new k(h, h.nextSibling, this, t) : 1 === r.type ? i = new r.ctor(h, r.name, r.strings, this, t) : 6 === r.type && (i = new Z(h, this, t)), this._$AV.push(i), r = s[++n];
			}
			o !== r?.index && (h = P.nextNode(), o++);
		}
		return P.currentNode = l, e;
	}
	p(t) {
		let i = 0;
		for (const s of this._$AV) void 0 !== s && (void 0 !== s.strings ? (s._$AI(t, s, i), i += s.strings.length - 2) : s._$AI(t[i])), i++;
	}
};
var k = class k {
	get _$AU() {
		return this._$AM?._$AU ?? this._$Cv;
	}
	constructor(t, i, s, e) {
		this.type = 2, this._$AH = A, this._$AN = void 0, this._$AA = t, this._$AB = i, this._$AM = s, this.options = e, this._$Cv = e?.isConnected ?? !0;
	}
	get parentNode() {
		let t = this._$AA.parentNode;
		const i = this._$AM;
		return void 0 !== i && 11 === t?.nodeType && (t = i.parentNode), t;
	}
	get startNode() {
		return this._$AA;
	}
	get endNode() {
		return this._$AB;
	}
	_$AI(t, i = this) {
		t = M(this, t, i), a(t) ? t === A || null == t || "" === t ? (this._$AH !== A && this._$AR(), this._$AH = A) : t !== this._$AH && t !== E && this._(t) : void 0 !== t._$litType$ ? this.$(t) : void 0 !== t.nodeType ? this.T(t) : d(t) ? this.k(t) : this._(t);
	}
	O(t) {
		return this._$AA.parentNode.insertBefore(t, this._$AB);
	}
	T(t) {
		this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
	}
	_(t) {
		this._$AH !== A && a(this._$AH) ? this._$AA.nextSibling.data = t : this.T(l.createTextNode(t)), this._$AH = t;
	}
	$(t) {
		const { values: i, _$litType$: s } = t, e = "number" == typeof s ? this._$AC(t) : (void 0 === s.el && (s.el = S.createElement(V(s.h, s.h[0]), this.options)), s);
		if (this._$AH?._$AD === e) this._$AH.p(i);
		else {
			const t = new R(e, this), s = t.u(this.options);
			t.p(i), this.T(s), this._$AH = t;
		}
	}
	_$AC(t) {
		let i = C.get(t.strings);
		return void 0 === i && C.set(t.strings, i = new S(t)), i;
	}
	k(t) {
		u(this._$AH) || (this._$AH = [], this._$AR());
		const i = this._$AH;
		let s, e = 0;
		for (const h of t) e === i.length ? i.push(s = new k(this.O(c()), this.O(c()), this, this.options)) : s = i[e], s._$AI(h), e++;
		e < i.length && (this._$AR(s && s._$AB.nextSibling, e), i.length = e);
	}
	_$AR(t = this._$AA.nextSibling, s) {
		for (this._$AP?.(!1, !0, s); t !== this._$AB;) {
			const s = i$1(t).nextSibling;
			i$1(t).remove(), t = s;
		}
	}
	setConnected(t) {
		void 0 === this._$AM && (this._$Cv = t, this._$AP?.(t));
	}
};
var H = class {
	get tagName() {
		return this.element.tagName;
	}
	get _$AU() {
		return this._$AM._$AU;
	}
	constructor(t, i, s, e, h) {
		this.type = 1, this._$AH = A, this._$AN = void 0, this.element = t, this.name = i, this._$AM = e, this.options = h, s.length > 2 || "" !== s[0] || "" !== s[1] ? (this._$AH = Array(s.length - 1).fill(/* @__PURE__ */ new String()), this.strings = s) : this._$AH = A;
	}
	_$AI(t, i = this, s, e) {
		const h = this.strings;
		let o = !1;
		if (void 0 === h) t = M(this, t, i, 0), o = !a(t) || t !== this._$AH && t !== E, o && (this._$AH = t);
		else {
			const e = t;
			let n, r;
			for (t = h[0], n = 0; n < h.length - 1; n++) r = M(this, e[s + n], i, n), r === E && (r = this._$AH[n]), o ||= !a(r) || r !== this._$AH[n], r === A ? t = A : t !== A && (t += (r ?? "") + h[n + 1]), this._$AH[n] = r;
		}
		o && !e && this.j(t);
	}
	j(t) {
		t === A ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t ?? "");
	}
};
var I = class extends H {
	constructor() {
		super(...arguments), this.type = 3;
	}
	j(t) {
		this.element[this.name] = t === A ? void 0 : t;
	}
};
var L = class extends H {
	constructor() {
		super(...arguments), this.type = 4;
	}
	j(t) {
		this.element.toggleAttribute(this.name, !!t && t !== A);
	}
};
var z = class extends H {
	constructor(t, i, s, e, h) {
		super(t, i, s, e, h), this.type = 5;
	}
	_$AI(t, i = this) {
		if ((t = M(this, t, i, 0) ?? A) === E) return;
		const s = this._$AH, e = t === A && s !== A || t.capture !== s.capture || t.once !== s.once || t.passive !== s.passive, h = t !== A && (s === A || e);
		e && this.element.removeEventListener(this.name, this, s), h && this.element.addEventListener(this.name, this, t), this._$AH = t;
	}
	handleEvent(t) {
		"function" == typeof this._$AH ? this._$AH.call(this.options?.host ?? this.element, t) : this._$AH.handleEvent(t);
	}
};
var Z = class {
	constructor(t, i, s) {
		this.element = t, this.type = 6, this._$AN = void 0, this._$AM = i, this.options = s;
	}
	get _$AU() {
		return this._$AM._$AU;
	}
	_$AI(t) {
		M(this, t);
	}
};
var B = t.litHtmlPolyfillSupport;
B?.(S, k), (t.litHtmlVersions ??= []).push("3.3.3");
var D = (t, i, s) => {
	const e = s?.renderBefore ?? i;
	let h = e._$litPart$;
	if (void 0 === h) {
		const t = s?.renderBefore ?? null;
		e._$litPart$ = h = new k(i.insertBefore(c(), t), t, void 0, s ?? {});
	}
	return h._$AI(t), h;
};
//#endregion
//#region node_modules/lit-element/lit-element.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var s = globalThis;
var i = class extends y$1 {
	constructor() {
		super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
	}
	createRenderRoot() {
		const t = super.createRenderRoot();
		return this.renderOptions.renderBefore ??= t.firstChild, t;
	}
	update(t) {
		const r = this.render();
		this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t), this._$Do = D(r, this.renderRoot, this.renderOptions);
	}
	connectedCallback() {
		super.connectedCallback(), this._$Do?.setConnected(!0);
	}
	disconnectedCallback() {
		super.disconnectedCallback(), this._$Do?.setConnected(!1);
	}
	render() {
		return E;
	}
};
i._$litElement$ = !0, i["finalized"] = !0, s.litElementHydrateSupport?.({ LitElement: i });
var o = s.litElementPolyfillSupport;
o?.({ LitElement: i });
(s.litElementVersions ??= []).push("4.2.2");
//#endregion
//#region src/api.js
async function getJson(path, { signal } = {}) {
	const response = await fetch(path, {
		headers: { Accept: "application/json" },
		signal
	});
	if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
	return response.json();
}
async function mutationJson(path, method, body, { signal } = {}) {
	const response = await fetch(path, {
		method,
		headers: {
			Accept: "application/json",
			...body === void 0 ? {} : { "Content-Type": "application/json" }
		},
		...body === void 0 ? {} : { body: JSON.stringify(body) },
		signal
	});
	const payload = await response.json().catch(() => void 0);
	if (!response.ok) throw new Error(payload?.detail ?? `${response.status} ${response.statusText}`);
	return payload;
}
function putJson(path, body, options) {
	return mutationJson(path, "PUT", body, options);
}
function postJson(path, body, options) {
	return mutationJson(path, "POST", body, options);
}
function deleteJson(path, options) {
	return mutationJson(path, "DELETE", void 0, options);
}
//#endregion
//#region src/live-resource.js
var LiveResource = class {
	value;
	error;
	loading = true;
	#host;
	#load;
	#interval;
	#timer;
	#request;
	#connected = false;
	constructor(host, load, { interval = 3e4 } = {}) {
		this.#host = host;
		this.#load = load;
		this.#interval = interval;
		host.addController(this);
	}
	hostConnected() {
		this.#connected = true;
		this.refresh();
	}
	hostDisconnected() {
		this.#connected = false;
		clearTimeout(this.#timer);
		this.#request?.abort();
	}
	async refresh() {
		clearTimeout(this.#timer);
		this.#request?.abort();
		const request = new AbortController();
		this.#request = request;
		this.loading = true;
		this.error = void 0;
		this.#host.requestUpdate();
		try {
			this.value = await this.#load(request.signal);
		} catch (error) {
			if (error.name !== "AbortError") this.error = error;
		} finally {
			if (this.#request === request) {
				this.loading = false;
				this.#request = void 0;
				this.#host.requestUpdate();
				if (this.#connected && this.#interval > 0) this.#timer = setTimeout(() => this.refresh(), this.#interval);
			}
		}
	}
};
//#endregion
//#region src/format.js
function formatCurrency(value, currency = "EUR", fractionDigits = 2) {
	if (value === null || value === void 0) return "-";
	return new Intl.NumberFormat("en-EU", {
		style: "currency",
		currency,
		minimumFractionDigits: fractionDigits,
		maximumFractionDigits: fractionDigits
	}).format(value);
}
function formatPercent(value, fractionDigits = 2) {
	if (value === null || value === void 0) return "-";
	return `${value > 0 ? "+" : ""}${value.toFixed(fractionDigits)}%`;
}
//#endregion
//#region src/modal-utils.js
function formatNumber(value, fractionDigits = 0) {
	const number = Number(value);
	return Number.isFinite(number) ? number.toLocaleString("en-GB", {
		minimumFractionDigits: fractionDigits,
		maximumFractionDigits: fractionDigits
	}) : "-";
}
function formatDateTime(value, { seconds = false } = {}) {
	if (value === null || value === void 0 || value === "") return "-";
	const date = seconds ? /* @__PURE__ */ new Date(Number(value) * 1e3) : new Date(value);
	if (Number.isNaN(date.getTime())) return "-";
	return date.toLocaleString("en-GB", {
		day: "2-digit",
		month: "short",
		year: "numeric",
		hour: "2-digit",
		minute: "2-digit"
	});
}
function formatRelativeTime(value) {
	if (!value) return "-";
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return "-";
	const seconds = Math.round((date.getTime() - Date.now()) / 1e3);
	const absolute = Math.abs(seconds);
	const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
	if (absolute < 60) return formatter.format(seconds, "second");
	if (absolute < 3600) return formatter.format(Math.round(seconds / 60), "minute");
	if (absolute < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
	return formatter.format(Math.round(seconds / 86400), "day");
}
function formatDuration(milliseconds) {
	const value = Number(milliseconds);
	if (!Number.isFinite(value)) return "-";
	if (value < 1e3) return `${Math.round(value)} ms`;
	const seconds = value / 1e3;
	if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} sec`;
	return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} sec`;
}
function statusVariant(status) {
	if ([
		"completed",
		"done",
		"fresh",
		"enabled"
	].includes(status)) return "success";
	if ([
		"failed",
		"error",
		"invalid"
	].includes(status)) return "error";
	if ([
		"queued",
		"running",
		"stale"
	].includes(status)) return "warning";
}
function dateInputValue(date) {
	const offset = date.getTimezoneOffset() * 6e4;
	return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}
//#endregion
//#region src/sentinel-backtest.js
var phaseLabels = {
	prepare_db: "Preparing database…",
	discover_symbols: "Discovering securities…",
	download_prices: "Downloading historical data…",
	calculate_scores: "Calculating scores…",
	simulate: "Running simulation…"
};
var SentinelBacktest = class extends i {
	static properties = {
		startDate: { state: true },
		endDate: { state: true },
		initialCapital: { state: true },
		monthlyDeposit: { state: true },
		rebalanceFrequency: { state: true },
		useExistingUniverse: { state: true },
		pickRandom: { state: true },
		randomCount: { state: true },
		symbols: { state: true },
		status: { state: true },
		progress: { state: true },
		currentDate: { state: true },
		portfolioValue: { state: true },
		errorMessage: { state: true },
		phase: { state: true },
		currentItem: { state: true },
		itemsDone: { state: true },
		itemsTotal: { state: true },
		result: { state: true }
	};
	constructor() {
		super();
		const yesterday = /* @__PURE__ */ new Date();
		yesterday.setDate(yesterday.getDate() - 1);
		const fiveYearsAgo = /* @__PURE__ */ new Date();
		fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5);
		this.startDate = dateInputValue(fiveYearsAgo);
		this.endDate = dateInputValue(yesterday);
		this.initialCapital = 1e4;
		this.monthlyDeposit = 500;
		this.rebalanceFrequency = "weekly";
		this.useExistingUniverse = true;
		this.pickRandom = true;
		this.randomCount = 10;
		this.symbols = "";
		this.reset();
	}
	createRenderRoot() {
		return this;
	}
	disconnectedCallback() {
		if (this.status === "running") {
			this.eventSource?.close();
			fetch("/api/backtest/cancel", { method: "POST" }).catch(() => {});
		}
		super.disconnectedCallback();
	}
	reset() {
		this.eventSource?.close();
		this.eventSource = void 0;
		this.status = "idle";
		this.progress = 0;
		this.currentDate = "";
		this.portfolioValue = 0;
		this.errorMessage = "";
		this.phase = "";
		this.currentItem = "";
		this.itemsDone = 0;
		this.itemsTotal = 0;
		this.result = void 0;
	}
	fieldValue(event) {
		return event.currentTarget.value;
	}
	startBacktest(event) {
		event.preventDefault();
		this.reset();
		this.status = "running";
		const parameters = new URLSearchParams({
			start_date: this.startDate,
			end_date: this.endDate,
			initial_capital: String(this.initialCapital),
			monthly_deposit: String(this.monthlyDeposit),
			rebalance_frequency: this.rebalanceFrequency,
			use_existing_universe: String(this.useExistingUniverse),
			pick_random: String(this.pickRandom),
			random_count: String(this.randomCount),
			symbols: this.symbols
		});
		const source = new EventSource(`/api/backtest/run?${parameters}`);
		this.eventSource = source;
		source.addEventListener("progress", (eventSourceEvent) => {
			const data = JSON.parse(eventSourceEvent.data);
			this.progress = data.progress_pct ?? 0;
			this.currentDate = data.current_date ?? "";
			this.portfolioValue = data.portfolio_value ?? 0;
			this.phase = data.phase ?? "";
			this.currentItem = data.current_item ?? "";
			this.itemsDone = data.items_done ?? 0;
			this.itemsTotal = data.items_total ?? 0;
			if (data.status === "error") {
				this.status = "error";
				this.errorMessage = data.message || "Unknown error";
				source.close();
			} else if (data.status === "cancelled") {
				this.status = "idle";
				source.close();
			}
		});
		source.addEventListener("result", (eventSourceEvent) => {
			this.result = JSON.parse(eventSourceEvent.data);
			this.status = "completed";
			source.close();
		});
		source.addEventListener("error", () => {
			if (source.readyState !== EventSource.CLOSED) {
				this.status = "error";
				this.errorMessage = "Connection lost";
				source.close();
			}
		});
	}
	async cancelBacktest() {
		this.eventSource?.close();
		this.eventSource = void 0;
		try {
			await fetch("/api/backtest/cancel", { method: "POST" });
		} catch {}
		this.status = "idle";
	}
	renderIdle() {
		return b`
      <form @submit=${this.startBacktest}>
        <div>
          <label
            >Start date&nbsp;<tui-input
              type="date"
              value=${this.startDate}
              max=${this.endDate}
              required
              @change=${(event) => this.startDate = this.fieldValue(event)}
            ></tui-input
          ></label>
        </div>
        <div>
          <label
            >End date&nbsp;<tui-input
              type="date"
              value=${this.endDate}
              min=${this.startDate}
              max=${dateInputValue(/* @__PURE__ */ new Date(Date.now() - 864e5))}
              required
              @change=${(event) => this.endDate = this.fieldValue(event)}
            ></tui-input
          ></label>
        </div>
        <div>
          <label
            >Initial capital (EUR)&nbsp;<tui-input
              type="number"
              value=${this.initialCapital}
              min="100"
              max="10000000"
              step="1000"
              required
              @change=${(event) => this.initialCapital = Number(this.fieldValue(event))}
            ></tui-input
          ></label>
          <div>Starting portfolio value in EUR</div>
        </div>
        <div>
          <label
            >Monthly deposit (EUR)&nbsp;<tui-input
              type="number"
              value=${this.monthlyDeposit}
              min="0"
              max="100000"
              step="100"
              required
              @change=${(event) => this.monthlyDeposit = Number(this.fieldValue(event))}
            ></tui-input
          ></label>
          <div>Amount to add on the first of each month</div>
        </div>
        <div>
          <label
            >Rebalance frequency&nbsp;<tui-select
              value=${this.rebalanceFrequency}
              @change=${(event) => this.rebalanceFrequency = this.fieldValue(event)}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly (Recommended)</option>
              <option value="monthly">Monthly</option>
            </tui-select></label
          >
        </div>
        <div aria-hidden="true">&nbsp;</div>
        <tui-box heading="Securities Selection" border="single">
          <div>
            <tui-toggle
              ?checked=${this.useExistingUniverse}
              @change=${(event) => this.useExistingUniverse = event.currentTarget.checked}
              >Use existing universe</tui-toggle
            >
          </div>
          <div>Use all active securities from the current database</div>
          ${!this.useExistingUniverse ? b`
                  <div>
                    <tui-toggle
                      ?checked=${this.pickRandom}
                      @change=${(event) => this.pickRandom = event.currentTarget.checked}
                      >Pick random securities</tui-toggle
                    >
                  </div>
                  ${this.pickRandom ? b`<label
                          >Number of securities&nbsp;<tui-input
                            type="number"
                            value=${this.randomCount}
                            min="1"
                            max="100"
                            @change=${(event) => this.randomCount = Number(this.fieldValue(event))}
                          ></tui-input
                        ></label>` : b`<label
                          >Symbols&nbsp;<tui-input
                            value=${this.symbols}
                            placeholder="AAPL.US, MSFT.US, GOOGL.US"
                            size="40"
                            @input=${(event) => this.symbols = this.fieldValue(event)}
                          ></tui-input
                        ></label>`}
                ` : ""}
        </tui-box>
        <div aria-hidden="true">&nbsp;</div>
        <tui-button type="submit">Run Backtest</tui-button>
      </form>
    `;
	}
	renderRunning() {
		return b`
      <div aria-live="polite">
        <div>${phaseLabels[this.phase] ?? "Starting backtest…"}</div>
        <tui-progress
          aria-label="Backtest progress"
          value=${this.progress}
          columns="30"
        ></tui-progress>
        ${this.phase === "download_prices" && this.itemsTotal > 0 ? b`<div>
                ${this.currentItem ? `Processing: ${this.currentItem} │ ` : ""}
                ${this.itemsDone} / ${this.itemsTotal} symbols
              </div>` : ""}
        ${this.phase === "simulate" ? b`<div>
                Simulating: ${this.currentDate} │
                ${Number(this.progress).toFixed(1)}%
              </div>` : ""}
        ${this.portfolioValue > 0 && this.phase === "simulate" ? b`<div>
                Portfolio value:
                ${formatCurrency(this.portfolioValue, "EUR", 0)}
              </div>` : ""}
        <div aria-hidden="true">&nbsp;</div>
        <tui-button variant="error" @click=${this.cancelBacktest}
          >Cancel</tui-button
        >
      </div>
    `;
	}
	renderResult() {
		const values = (this.result?.snapshots ?? []).map((snapshot) => snapshot.total_value);
		return b`
      <div>
        Total invested ${formatCurrency(this.result.total_deposits, "EUR", 0)} │
        Final value ${formatCurrency(this.result.final_value, "EUR", 0)} │
        <tui-text variant=${this.result.total_return >= 0 ? "success" : "error"}
          >Return ${formatCurrency(this.result.total_return, "EUR", 0)}
          (${formatPercent(this.result.total_return_pct, 2)})</tui-text
        >
      </div>
      <div>
        <tui-text variant=${this.result.cagr >= 0 ? "success" : "error"}
          >CAGR ${formatPercent(this.result.cagr, 2)}</tui-text
        >
        │
        <tui-text variant="warning"
          >Max drawdown -${formatNumber(this.result.max_drawdown, 2)}%</tui-text
        >
        │ Sharpe ${formatNumber(this.result.sharpe_ratio, 2)}
      </div>
      <div aria-hidden="true">&nbsp;</div>
      <tui-box heading="Equity Curve" border="single">
        ${values.length > 1 ? b`<tui-chart
                height="6"
                aria-label="Backtest equity curve"
                .values=${values}
              ></tui-chart>` : "No equity curve data"}
      </tui-box>
      ${this.result.security_performance?.length ? b`
              <div aria-hidden="true">&nbsp;</div>
              <tui-box heading="Security Performance" border="single">
                <div style="overflow: auto; min-width: 0">
                  <table style="border-collapse: collapse; width: 100%">
                    <thead>
                      <tr>
                        <th style="text-align: left">Symbol</th>
                        <th style="text-align: left">│ Invested</th>
                        <th style="text-align: left">│ Final value</th>
                        <th style="text-align: left">│ Return</th>
                        <th style="text-align: left">│ Trades</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${this.result.security_performance.map((security) => b`
                          <tr>
                            <td style="text-align: left; vertical-align: top">
                              ${security.symbol}<br />${security.name ?? ""}
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │
                              ${formatCurrency(security.total_invested, "EUR", 0)}
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │
                              ${formatCurrency(security.final_value, "EUR", 0)}
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │
                              <tui-text
                                variant=${security.total_return >= 0 ? "success" : "error"}
                                >${formatPercent(security.return_pct, 2)}</tui-text
                              >
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │ ${security.num_buys} buys, ${security.num_sells}
                              sells
                            </td>
                          </tr>
                        `)}
                    </tbody>
                  </table>
                </div>
              </tui-box>
            ` : ""}
      <div>
        Total trades: ${this.result.trades?.length ?? 0} │
        <tui-button @click=${this.reset}>Run Another Backtest</tui-button>
      </div>
    `;
	}
	render() {
		if (this.status === "running") return this.renderRunning();
		if (this.status === "error") return b`
        <tui-text variant="error"
          >Backtest failed: ${this.errorMessage}</tui-text
        >
        <div><tui-button @click=${this.reset}>Try Again</tui-button></div>
      `;
		if (this.status === "completed" && this.result) return this.renderResult();
		return this.renderIdle();
	}
};
customElements.define("sentinel-backtest", SentinelBacktest);
//#endregion
//#region \0vite/preload-helper.js
var scriptRel = "modulepreload";
var assetsURL = function(dep) {
	return "/" + dep;
};
var seen = {};
var __vitePreload = function preload(baseModule, deps, importerUrl) {
	let promise = Promise.resolve();
	if (deps && deps.length > 0) {
		const links = document.getElementsByTagName("link");
		const cspNonceMeta = document.querySelector("meta[property=csp-nonce]");
		const cspNonce = cspNonceMeta?.nonce || cspNonceMeta?.getAttribute("nonce");
		function allSettled(promises) {
			return Promise.all(promises.map((p) => Promise.resolve(p).then((value) => ({
				status: "fulfilled",
				value
			}), (reason) => ({
				status: "rejected",
				reason
			}))));
		}
		function importMetaResolve(specifier) {
			if (import.meta.resolve) return import.meta.resolve(specifier);
			return new URL(
				specifier,
				/** #__KEEP__ */
				import.meta.url
			).href;
		}
		promise = allSettled(deps.map((dep) => {
			dep = assetsURL(dep, importerUrl);
			dep = importMetaResolve(dep);
			if (dep in seen) return;
			seen[dep] = true;
			const isCss = dep.endsWith(".css");
			for (let i = links.length - 1; i >= 0; i--) {
				const link = links[i];
				if (link.href === dep && (!isCss || link.rel === "stylesheet")) return;
			}
			const link = document.createElement("link");
			link.rel = isCss ? "stylesheet" : scriptRel;
			if (!isCss) link.as = "script";
			link.crossOrigin = "";
			link.href = dep;
			if (cspNonce) link.setAttribute("nonce", cspNonce);
			document.head.appendChild(link);
			if (isCss) return new Promise((res, rej) => {
				link.addEventListener("load", res);
				link.addEventListener("error", () => rej(/* @__PURE__ */ new Error(`Unable to preload CSS for ${dep}`)));
			});
		}));
	}
	function handlePreloadError(err) {
		const e = new Event("vite:preloadError", { cancelable: true });
		e.payload = err;
		window.dispatchEvent(e);
		if (!e.defaultPrevented) throw err;
	}
	return promise.then((res) => {
		for (const item of res || []) {
			if (item.status !== "rejected") continue;
			handlePreloadError(item.reason);
		}
		return baseModule().catch(handlePreloadError);
	});
};
//#endregion
//#region src/sentinel-code-editor.js
var SentinelCodeEditor = class extends HTMLElement {
	static observedAttributes = [
		"aria-label",
		"color-scheme",
		"disabled",
		"document-id",
		"filename",
		"height",
		"language"
	];
	#value = "";
	#view;
	#runtime;
	#fallback;
	#initialization = 0;
	#languageLoad = 0;
	#colorSchemeLoad = 0;
	#documentSyncQueued = false;
	connectedCallback() {
		this.style.display = "block";
		this.style.height = this.editorHeight;
		this.style.maxWidth = "100%";
		this.style.minWidth = "0";
		this.style.overflow = "hidden";
		this.#showFallback();
		this.#initialize();
	}
	disconnectedCallback() {
		this.#initialization += 1;
		this.#languageLoad += 1;
		this.#colorSchemeLoad += 1;
		this.#view?.destroy();
		this.#view = void 0;
		this.#runtime = void 0;
		this.#fallback = void 0;
	}
	attributeChangedCallback(name) {
		if (name === "height") {
			this.style.height = this.editorHeight;
			return;
		}
		if (name === "disabled") {
			this.#syncDisabled();
			return;
		}
		if (name === "aria-label") {
			this.#syncAriaLabel();
			return;
		}
		if (name === "color-scheme") {
			this.#syncColorScheme();
			return;
		}
		if (name === "document-id") {
			this.#queueDocumentSync();
			return;
		}
		if (name === "filename" || name === "language") this.#syncLanguage();
	}
	get value() {
		return this.#value;
	}
	set value(value) {
		const next = String(value ?? "");
		if (next === this.#value) return;
		this.#value = next;
		if (this.#fallback && this.#fallback.value !== next) this.#fallback.value = next;
		this.#queueDocumentSync();
	}
	get documentId() {
		return this.getAttribute("document-id") ?? "";
	}
	get filename() {
		return this.getAttribute("filename") ?? "";
	}
	get language() {
		return (this.getAttribute("language") || "plaintext").trim().toLowerCase();
	}
	get disabled() {
		return this.hasAttribute("disabled");
	}
	get editorHeight() {
		return this.getAttribute("height") || "30lh";
	}
	get colorScheme() {
		const value = this.getAttribute("color-scheme") || "monochrome";
		return [
			"monochrome",
			"latte",
			"frappe",
			"macchiato",
			"mocha"
		].includes(value) ? value : "monochrome";
	}
	get editorLabel() {
		return this.getAttribute("aria-label") || "Code editor";
	}
	focus(options) {
		if (this.#view) this.#view.focus();
		else this.#fallback?.focus(options);
	}
	#showFallback() {
		const textarea = document.createElement("textarea");
		textarea.value = this.#value;
		textarea.disabled = this.disabled;
		textarea.spellcheck = false;
		textarea.setAttribute("aria-label", this.editorLabel);
		textarea.style.boxSizing = "border-box";
		textarea.style.display = "block";
		textarea.style.height = "100%";
		textarea.style.width = "100%";
		textarea.style.background = "var(--tui-background)";
		textarea.style.color = "var(--tui-color)";
		textarea.style.font = "inherit";
		textarea.addEventListener("input", (event) => {
			event.stopPropagation();
			this.#value = textarea.value;
			this.dispatchEvent(new Event("input", {
				bubbles: true,
				composed: true
			}));
		});
		this.replaceChildren(textarea);
		this.#fallback = textarea;
	}
	async #initialize() {
		const initialization = ++this.#initialization;
		try {
			const [{ basicSetup, EditorView }, { Compartment, EditorState }, { markdown }, { languages }, { LanguageDescription }] = await Promise.all([
				__vitePreload(() => import("./dist-qUpxMwR-.js"), __vite__mapDeps([0,1,2,3])),
				__vitePreload(() => import("./dist-CzEUVXDC.js").then((n) => n.x), []),
				__vitePreload(() => import("./dist-CtvrPQL3.js"), __vite__mapDeps([4,1,2,3,5,6,7,8])),
				__vitePreload(() => import("./dist-BhbiT-ju.js"), __vite__mapDeps([9,2,1])),
				__vitePreload(() => import("./dist-CFtxRP70.js"), __vite__mapDeps([2,1]))
			]);
			if (!this.isConnected || initialization !== this.#initialization) return;
			const languageCompartment = new Compartment();
			const colorSchemeCompartment = new Compartment();
			const editableCompartment = new Compartment();
			const readOnlyCompartment = new Compartment();
			const ariaCompartment = new Compartment();
			const initialLanguageKey = this.#languageKey();
			const initialColorScheme = this.colorScheme;
			const languageExtension = await this.#loadLanguageExtension({
				LanguageDescription,
				languages,
				markdown
			});
			const colorSchemeExtension = await this.#loadColorSchemeExtension({ EditorView }, initialColorScheme);
			if (!this.isConnected || initialization !== this.#initialization) return;
			const layoutTheme = EditorView.theme({
				"&": {
					height: "100%",
					maxWidth: "100%",
					fontSize: "inherit"
				},
				".cm-scroller": {
					height: "100%",
					fontFamily: "var(--tui-font-family)",
					lineHeight: "inherit",
					overflow: "auto"
				},
				".cm-content": { padding: "0" },
				".cm-line": { padding: "0 1ch" },
				".cm-gutters": { border: "0" },
				".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "transparent" },
				"&.cm-focused": { outline: "none" }
			});
			const runtime = {
				EditorState,
				EditorView,
				LanguageDescription,
				languages,
				markdown,
				languageCompartment,
				colorSchemeCompartment,
				editableCompartment,
				readOnlyCompartment,
				ariaCompartment,
				languageExtension,
				languageKey: initialLanguageKey,
				colorSchemeExtension,
				colorScheme: initialColorScheme,
				documentId: this.documentId,
				lastDocument: this.#value
			};
			runtime.buildState = (document) => EditorState.create({
				doc: document,
				extensions: [
					basicSetup,
					languageCompartment.of(runtime.languageExtension),
					EditorView.lineWrapping,
					ariaCompartment.of(EditorView.contentAttributes.of({ "aria-label": this.editorLabel })),
					layoutTheme,
					colorSchemeCompartment.of(runtime.colorSchemeExtension),
					editableCompartment.of(EditorView.editable.of(!this.disabled)),
					readOnlyCompartment.of(EditorState.readOnly.of(this.disabled)),
					EditorView.updateListener.of((update) => {
						if (!update.docChanged) return;
						const next = update.state.doc.toString();
						if (next === runtime.lastDocument) return;
						runtime.lastDocument = next;
						this.#value = next;
						this.dispatchEvent(new Event("input", {
							bubbles: true,
							composed: true
						}));
					})
				]
			});
			this.#runtime = runtime;
			this.replaceChildren();
			this.#fallback = void 0;
			this.#view = new EditorView({
				state: runtime.buildState(this.#value),
				parent: this
			});
			this.#syncLanguage();
			this.#syncColorScheme();
		} catch (error) {
			console.error("Failed to load Sentinel code editor", error);
		}
	}
	async #loadLanguageExtension(runtime = this.#runtime) {
		if (!runtime) return [];
		const normalized = this.language;
		if (!normalized || normalized === "plaintext" || normalized === "text") return [];
		if (normalized === "markdown") return runtime.markdown({ codeLanguages: runtime.languages });
		const description = runtime.LanguageDescription.matchLanguageName(runtime.languages, normalized, true) || (this.filename ? runtime.LanguageDescription.matchFilename(runtime.languages, this.filename) : void 0);
		return description ? (await description.load()).extension : [];
	}
	async #syncLanguage() {
		const runtime = this.#runtime;
		const view = this.#view;
		if (!runtime || !view) return;
		const nextKey = this.#languageKey();
		if (nextKey === runtime.languageKey) return;
		const languageLoad = ++this.#languageLoad;
		const extension = await this.#loadLanguageExtension(runtime);
		if (languageLoad !== this.#languageLoad || runtime !== this.#runtime || view !== this.#view) return;
		runtime.languageExtension = extension;
		runtime.languageKey = nextKey;
		view.dispatch({ effects: runtime.languageCompartment.reconfigure(extension) });
	}
	#languageKey() {
		return `${this.language}\n${this.filename}`;
	}
	async #loadColorSchemeExtension(runtime, colorScheme) {
		if (colorScheme === "monochrome") return runtime.EditorView.theme({
			"&": {
				backgroundColor: "var(--tui-background)",
				color: "var(--tui-color)"
			},
			".cm-gutters": {
				backgroundColor: "var(--tui-background)",
				color: "var(--tui-color)",
				border: "0"
			},
			".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--tui-color)" },
			".cm-content *": { color: "var(--tui-color) !important" }
		});
		const { catppuccinFrappe, catppuccinLatte, catppuccinMacchiato, catppuccinMocha } = await __vitePreload(async () => {
			const { catppuccinFrappe, catppuccinLatte, catppuccinMacchiato, catppuccinMocha } = await import("./dist-DGm0tJyr.js");
			return {
				catppuccinFrappe,
				catppuccinLatte,
				catppuccinMacchiato,
				catppuccinMocha
			};
		}, __vite__mapDeps([10,2,1]));
		return {
			latte: catppuccinLatte,
			frappe: catppuccinFrappe,
			macchiato: catppuccinMacchiato,
			mocha: catppuccinMocha
		}[colorScheme];
	}
	async #syncColorScheme() {
		const runtime = this.#runtime;
		const view = this.#view;
		if (!runtime || !view) return;
		const nextColorScheme = this.colorScheme;
		if (nextColorScheme === runtime.colorScheme) return;
		const colorSchemeLoad = ++this.#colorSchemeLoad;
		const extension = await this.#loadColorSchemeExtension(runtime, nextColorScheme);
		if (colorSchemeLoad !== this.#colorSchemeLoad || runtime !== this.#runtime || view !== this.#view) return;
		runtime.colorSchemeExtension = extension;
		runtime.colorScheme = nextColorScheme;
		view.dispatch({ effects: runtime.colorSchemeCompartment.reconfigure(extension) });
	}
	#queueDocumentSync() {
		if (this.#documentSyncQueued) return;
		this.#documentSyncQueued = true;
		queueMicrotask(() => {
			this.#documentSyncQueued = false;
			this.#syncDocument();
		});
	}
	#syncDocument() {
		const runtime = this.#runtime;
		const view = this.#view;
		if (!runtime || !view) return;
		if (runtime.documentId !== this.documentId) {
			runtime.documentId = this.documentId;
			runtime.lastDocument = this.#value;
			view.setState(runtime.buildState(this.#value));
			return;
		}
		if (runtime.lastDocument === this.#value) return;
		runtime.lastDocument = this.#value;
		const head = Math.min(view.state.selection.main.head, this.#value.length);
		view.dispatch({
			changes: {
				from: 0,
				to: view.state.doc.length,
				insert: this.#value
			},
			selection: { anchor: head }
		});
	}
	#syncDisabled() {
		if (this.#fallback) this.#fallback.disabled = this.disabled;
		const runtime = this.#runtime;
		const view = this.#view;
		if (!runtime || !view) return;
		view.dispatch({ effects: [runtime.editableCompartment.reconfigure(runtime.EditorView.editable.of(!this.disabled)), runtime.readOnlyCompartment.reconfigure(runtime.EditorState.readOnly.of(this.disabled))] });
	}
	#syncAriaLabel() {
		this.#fallback?.setAttribute("aria-label", this.editorLabel);
		const runtime = this.#runtime;
		const view = this.#view;
		if (!runtime || !view) return;
		view.dispatch({ effects: runtime.ariaCompartment.reconfigure(runtime.EditorView.contentAttributes.of({ "aria-label": this.editorLabel })) });
	}
};
customElements.define("sentinel-code-editor", SentinelCodeEditor);
//#endregion
//#region src/sentinel-tasks.js
var editorColorSchemeKey = "sentinel.codeEditorColorScheme";
var editorColorSchemes = /* @__PURE__ */ new Set([
	"monochrome",
	"latte",
	"frappe",
	"macchiato",
	"mocha"
]);
var defaultCron = "0 9 * * *";
var defaultIntervalSeconds = 43200;
var cronFields = [
	{
		label: "Minute",
		options: [["*", "every minute"], ...[
			0,
			5,
			10,
			15,
			20,
			30,
			45
		].map((value) => [String(value), `:${String(value).padStart(2, "0")}`])]
	},
	{
		label: "Hour",
		options: [["*", "every hour"], ...Array.from({ length: 24 }, (_, value) => [String(value), value === 0 ? "midnight" : value === 12 ? "noon" : `${value > 12 ? value - 12 : value} ${value < 12 ? "AM" : "PM"}`])]
	},
	{
		label: "Day",
		options: [["*", "every day"], ...Array.from({ length: 31 }, (_, index) => [String(index + 1), String(index + 1)])]
	},
	{
		label: "Month",
		options: [["*", "every month"], ...[
			"January",
			"February",
			"March",
			"April",
			"May",
			"June",
			"July",
			"August",
			"September",
			"October",
			"November",
			"December"
		].map((label, index) => [String(index + 1), label])]
	},
	{
		label: "Weekday",
		options: [["*", "every day"], ...[
			"Sunday",
			"Monday",
			"Tuesday",
			"Wednesday",
			"Thursday",
			"Friday",
			"Saturday"
		].map((label, index) => [String(index), label])]
	}
].map((field, index) => ({
	...field,
	index
}));
function parseMetadata(content) {
	let raw = {};
	try {
		raw = JSON.parse(content);
	} catch {}
	return {
		name: typeof raw.name === "string" ? raw.name : "",
		enabled: raw.enabled === true,
		description: typeof raw.description === "string" ? raw.description : "",
		tags: Array.isArray(raw.tags) ? raw.tags.filter((tag) => typeof tag === "string") : [],
		cwd: typeof raw.cwd === "string" ? raw.cwd : "",
		timeout: typeof raw.timeout === "number" ? raw.timeout : "",
		schedule: typeof raw.schedule === "string" && raw.schedule.trim() ? raw.schedule : null,
		schedulePolicy: raw.schedulePolicy && typeof raw.schedulePolicy === "object" ? raw.schedulePolicy : null
	};
}
var SentinelTasks = class extends i {
	static properties = {
		tasks: { state: true },
		selectedId: { state: true },
		task: { state: true },
		files: { state: true },
		activeFile: { state: true },
		drafts: { state: true },
		baselines: { state: true },
		metadata: { state: true },
		metadataBaseline: { state: true },
		tab: { state: true },
		runInputs: { state: true },
		runs: { state: true },
		runId: { state: true },
		run: { state: true },
		loading: { state: true },
		busyAction: { state: true },
		notice: { state: true },
		actionError: { state: true },
		editorColorScheme: { state: true }
	};
	constructor() {
		super();
		this.tasks = [];
		this.selectedId = void 0;
		this.task = void 0;
		this.files = [];
		this.activeFile = void 0;
		this.drafts = {};
		this.baselines = {};
		this.metadata = void 0;
		this.metadataBaseline = "";
		this.tab = "files";
		this.runInputs = "{}";
		this.runs = [];
		this.runId = void 0;
		this.run = void 0;
		this.loading = true;
		this.busyAction = "";
		this.notice = "";
		this.actionError = "";
		const storedEditorColorScheme = globalThis.localStorage?.getItem(editorColorSchemeKey);
		this.editorColorScheme = editorColorSchemes.has(storedEditorColorScheme) ? storedEditorColorScheme : "monochrome";
	}
	createRenderRoot() {
		return this;
	}
	connectedCallback() {
		super.connectedCallback();
		this.loadTasks();
		this.tasksTimer = setInterval(() => this.loadTasks(true), 2e4);
		this.runsTimer = setInterval(() => this.pollRuns(), 2e3);
	}
	disconnectedCallback() {
		clearInterval(this.tasksTimer);
		clearInterval(this.runsTimer);
		super.disconnectedCallback();
	}
	get filesDirty() {
		return this.files.some((file) => file.name in this.baselines && this.drafts[file.name] !== this.baselines[file.name]);
	}
	get metadataDirty() {
		return this.metadata !== void 0 && JSON.stringify(this.metadata) !== this.metadataBaseline;
	}
	get dirty() {
		return this.filesDirty || this.metadataDirty;
	}
	get running() {
		return ["queued", "running"].includes(this.run?.status);
	}
	confirmClose() {
		if (!this.dirty) return true;
		return window.confirm(`Discard unsaved changes to "${this.task?.name || this.selectedId}"?`);
	}
	async loadTasks(background = false) {
		if (!background) this.loading = true;
		try {
			const tasks = await getJson("/api/tasks");
			this.tasks = tasks;
			if (!this.selectedId || !tasks.some((task) => task.id === this.selectedId)) {
				if (tasks[0]) await this.selectTask(tasks[0].id, { force: true });
			}
		} catch (error) {
			this.actionError = error.message;
		} finally {
			if (!background) this.loading = false;
		}
	}
	async selectTask(id, { force = false } = {}) {
		if (id === this.selectedId && this.task) return;
		if (!force && !this.confirmClose()) return;
		this.selectedId = id;
		this.task = void 0;
		this.files = [];
		this.activeFile = void 0;
		this.drafts = {};
		this.baselines = {};
		this.metadata = void 0;
		this.metadataBaseline = "";
		this.runs = [];
		this.runId = void 0;
		this.run = void 0;
		this.runInputs = "{}";
		this.notice = "";
		this.actionError = "";
		this.loading = true;
		try {
			const [task, files, runs, metadataFile] = await Promise.all([
				getJson(`/api/tasks/${encodeURIComponent(id)}`),
				getJson(`/api/tasks/${encodeURIComponent(id)}/files`),
				getJson(`/api/tasks/${encodeURIComponent(id)}/runs?limit=50`),
				getJson(`/api/tasks/${encodeURIComponent(id)}/files/${encodeURIComponent("task.json")}`)
			]);
			if (this.selectedId !== id) return;
			this.task = task;
			this.files = files;
			this.runs = runs;
			this.metadata = parseMetadata(metadataFile.content);
			this.metadataBaseline = JSON.stringify(this.metadata);
			const activeFile = files.find((file) => file.name === "task.js")?.name ?? files[0]?.name;
			if (activeFile) await this.selectFile(activeFile);
			const activeRun = runs.find((item) => ["queued", "running"].includes(item.status));
			this.runId = activeRun?.id ?? runs[0]?.id;
			if (this.runId) await this.loadRun(this.runId);
		} catch (error) {
			this.actionError = error.message;
		} finally {
			if (this.selectedId === id) this.loading = false;
		}
	}
	async selectFile(name) {
		this.activeFile = name;
		if (name in this.drafts) return;
		try {
			const file = await getJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/files/${encodeURIComponent(name)}`);
			this.drafts = {
				...this.drafts,
				[name]: file.content
			};
			this.baselines = {
				...this.baselines,
				[name]: file.content
			};
		} catch (error) {
			this.actionError = error.message;
		}
	}
	async pollRuns() {
		if (!this.selectedId) return;
		try {
			const runs = await getJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/runs?limit=50`);
			this.runs = runs;
			const active = runs.find((item) => ["queued", "running"].includes(item.status));
			if (active) this.runId = active.id;
			else if (this.runId && !runs.some((item) => item.id === this.runId)) this.runId = runs[0]?.id;
			if (this.runId) await this.loadRun(this.runId);
		} catch (error) {
			this.actionError = error.message;
		}
	}
	async loadRun(id) {
		this.runId = id;
		try {
			this.run = await getJson(`/api/task-runs/${encodeURIComponent(id)}`);
		} catch (error) {
			this.actionError = error.message;
		}
	}
	async createTask() {
		this.busyAction = "new";
		this.actionError = "";
		try {
			const task = await postJson("/api/tasks", { name: "New Task" });
			await this.loadTasks(true);
			await this.selectTask(task.id, { force: true });
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async deleteTask() {
		if (!this.task || !window.confirm(`Delete task "${this.task.name}"?`)) return;
		this.busyAction = "delete-task";
		try {
			await deleteJson(`/api/tasks/${encodeURIComponent(this.task.id)}`);
			this.selectedId = void 0;
			this.task = void 0;
			this.notice = "Deleted";
			await this.loadTasks();
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async validateTask() {
		this.busyAction = "validate";
		this.notice = "";
		this.actionError = "";
		try {
			const result = await getJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/validate`);
			this.notice = result.ok ? "Validation passed" : (result.errors ?? []).join("\n");
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async startRun() {
		let inputs;
		try {
			inputs = JSON.parse(this.runInputs);
			if (!inputs || Array.isArray(inputs) || typeof inputs !== "object") throw new Error("Inputs must be a JSON object");
		} catch (error) {
			this.actionError = `Invalid inputs: ${error.message}`;
			return;
		}
		this.busyAction = "run";
		this.notice = "";
		this.actionError = "";
		try {
			const run = await postJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/run`, { inputs });
			this.runId = run.id;
			this.run = run;
			await this.pollRuns();
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async stopRun() {
		if (!this.runId) return;
		this.busyAction = "stop";
		try {
			await deleteJson(`/api/task-runs/${encodeURIComponent(this.runId)}`);
			await this.pollRuns();
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	updateDraft(content) {
		this.drafts = {
			...this.drafts,
			[this.activeFile]: content
		};
	}
	async saveFile() {
		if (!this.activeFile) return;
		this.busyAction = "save-file";
		try {
			const content = this.drafts[this.activeFile] ?? "";
			await putJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/files/${encodeURIComponent(this.activeFile)}`, { content });
			this.baselines = {
				...this.baselines,
				[this.activeFile]: content
			};
			this.notice = "Saved";
			if (this.activeFile === "task.json") await this.loadTasks(true);
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	setEditorColorScheme(value) {
		this.editorColorScheme = editorColorSchemes.has(value) ? value : "monochrome";
		globalThis.localStorage?.setItem(editorColorSchemeKey, this.editorColorScheme);
	}
	async createFile() {
		const name = window.prompt("New file name (e.g. step.sh, prompt.md)")?.trim();
		if (!name) return;
		try {
			await postJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/files`, {
				name,
				content: ""
			});
			this.files = await getJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/files`);
			this.drafts = {
				...this.drafts,
				[name]: ""
			};
			this.baselines = {
				...this.baselines,
				[name]: ""
			};
			this.activeFile = name;
			this.notice = "Created";
		} catch (error) {
			this.actionError = error.message;
		}
	}
	async deleteFile(file) {
		if (!window.confirm(`Delete "${file.name}"? This cannot be undone.`)) return;
		try {
			await deleteJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/files/${encodeURIComponent(file.name)}`);
			const drafts = { ...this.drafts };
			const baselines = { ...this.baselines };
			delete drafts[file.name];
			delete baselines[file.name];
			this.drafts = drafts;
			this.baselines = baselines;
			this.files = this.files.filter((candidate) => candidate.name !== file.name);
			if (this.activeFile === file.name) {
				this.activeFile = void 0;
				if (this.files[0]) await this.selectFile(this.files[0].name);
			}
			this.notice = "Deleted";
		} catch (error) {
			this.actionError = error.message;
		}
	}
	patchMetadata(values) {
		this.metadata = {
			...this.metadata,
			...values
		};
	}
	get scheduleMode() {
		if (this.metadata?.schedule) return "cron";
		if ((this.metadata?.schedulePolicy?.staleAfterSeconds ?? 0) > 0) return "interval";
		return "off";
	}
	setScheduleMode(mode) {
		if (mode === "cron") this.patchMetadata({
			schedule: this.metadata.schedule || defaultCron,
			schedulePolicy: null
		});
		else if (mode === "interval") this.patchMetadata({
			schedule: null,
			schedulePolicy: {
				...this.metadata.schedulePolicy ?? {},
				staleAfterSeconds: this.metadata.schedulePolicy?.staleAfterSeconds ?? defaultIntervalSeconds,
				runWhen: this.metadata.schedulePolicy?.runWhen ?? "idle"
			}
		});
		else this.patchMetadata({
			schedule: null,
			schedulePolicy: null
		});
	}
	intervalParts() {
		const seconds = this.metadata?.schedulePolicy?.staleAfterSeconds ?? defaultIntervalSeconds;
		return {
			days: Math.floor(seconds / 86400),
			hours: Math.floor(seconds % 86400 / 3600),
			minutes: Math.floor(seconds % 3600 / 60)
		};
	}
	patchInterval(part, value) {
		const parts = {
			...this.intervalParts(),
			[part]: Math.max(0, Number(value))
		};
		const staleAfterSeconds = Math.max(1, Math.floor(parts.days * 86400 + parts.hours * 3600 + parts.minutes * 60));
		this.patchMetadata({ schedulePolicy: {
			...this.metadata.schedulePolicy,
			staleAfterSeconds,
			runWhen: this.metadata.schedulePolicy?.runWhen ?? "idle"
		} });
	}
	patchSchedulePolicy(values) {
		this.patchMetadata({ schedulePolicy: {
			...this.metadata.schedulePolicy,
			...values
		} });
	}
	cronParts() {
		const parts = (this.metadata?.schedule?.trim() || defaultCron).split(/\s+/);
		return parts.length === 5 ? parts : defaultCron.split(" ");
	}
	cronValues(index) {
		const part = this.cronParts()[index];
		return new Set(part === "*" ? ["*"] : part.split(",").filter(Boolean));
	}
	toggleCronValue(index, value, checked) {
		const values = this.cronValues(index);
		if (value === "*") {
			values.clear();
			values.add("*");
		} else if (checked) {
			values.delete("*");
			values.add(value);
		} else {
			values.delete(value);
			if (values.size === 0) values.add("*");
		}
		const parts = this.cronParts();
		parts[index] = values.has("*") ? "*" : [...values].sort((left, right) => Number(left) - Number(right)).join(",");
		this.patchMetadata({
			schedule: parts.join(" "),
			schedulePolicy: null
		});
	}
	async saveMetadata() {
		this.busyAction = "save-metadata";
		try {
			const payload = {
				name: this.metadata.name.trim() || "Untitled task",
				enabled: this.metadata.enabled,
				description: this.metadata.description.trim() || null,
				tags: this.metadata.tags.length ? this.metadata.tags : null,
				cwd: this.metadata.cwd.trim() || null,
				timeout: Number(this.metadata.timeout) > 0 ? Number(this.metadata.timeout) : null,
				schedule: this.metadata.schedule?.trim() || null,
				schedulePolicy: this.metadata.schedulePolicy || null
			};
			const task = await putJson(`/api/tasks/${encodeURIComponent(this.selectedId)}/meta`, payload);
			this.task = task;
			this.metadataBaseline = JSON.stringify(this.metadata);
			this.notice = "Saved";
			await this.loadTasks(true);
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	renderTaskList() {
		return b`
      <tui-box heading="Tasks" border="single">
        ${[
			["Invalid", this.tasks.filter((task) => task.invalid)],
			["Enabled", this.tasks.filter((task) => task.enabled && !task.invalid)],
			["Disabled", this.tasks.filter((task) => !task.enabled && !task.invalid)]
		].filter(([, tasks]) => tasks.length > 0).map(([label, tasks], index) => b`
            ${index > 0 ? b`<div aria-hidden="true">&nbsp;</div>` : ""}
            <div>${label}</div>
            ${tasks.map((task) => b`
                <div>
                  <span aria-hidden="true"
                    >${task.id === this.selectedId ? "▶" : " "}&nbsp;</span
                  ><tui-button
                    ?disabled=${this.running}
                    @click=${() => this.selectTask(task.id)}
                    >${task.name}</tui-button
                  >
                  <tui-text
                    variant=${task.invalid ? "error" : task.enabled ? "success" : ""}
                    >${task.invalid ? "invalid" : task.enabled ? "on" : "off"}</tui-text
                  >
                  <div>${task.id}</div>
                </div>
              `)}
          `)}
      </tui-box>
    `;
	}
	renderToolbar() {
		return b`
      <tui-flex align="baseline" justify="between" wrap>
        <span>
          ${this.task.name}
          ${this.dirty ? b`<tui-text variant="warning">unsaved</tui-text>` : ""}
          │ ${this.task.source} │ ${this.task.id}
        </span>
        <span>
          <tui-button
            ?disabled=${this.dirty || this.running || this.busyAction !== ""}
            @click=${this.validateTask}
            >Check</tui-button
          >
          ${this.running ? b`<tui-button variant="error" @click=${this.stopRun}
                  >Stop</tui-button
                >` : b`<tui-button
                  ?disabled=${this.dirty || this.task.invalid || this.busyAction !== ""}
                  @click=${this.startRun}
                  >Run</tui-button
                >`}
          <tui-button
            variant="error"
            ?disabled=${this.running || this.task.source === "core" || this.busyAction !== ""}
            @click=${this.deleteTask}
            >Delete</tui-button
          >
        </span>
      </tui-flex>
    `;
	}
	renderFiles() {
		const active = this.files.find((file) => file.name === this.activeFile);
		const draft = this.activeFile ? this.drafts[this.activeFile] ?? "" : "";
		const dirty = this.activeFile && this.activeFile in this.baselines && draft !== this.baselines[this.activeFile];
		return b`
      <tui-flex align="start" wrap>
        <tui-box
          heading="Files"
          border="single"
          style="flex: 1 1 20ch; min-width: 0"
        >
          <div><tui-button @click=${this.createFile}>New File</tui-button></div>
          ${this.files.map((file) => b`
              <div>
                <span aria-hidden="true"
                  >${file.name === this.activeFile ? "▶" : " "}&nbsp;</span
                ><tui-button
                  ?disabled=${this.running}
                  @click=${() => this.selectFile(file.name)}
                  >${file.name}</tui-button
                >
                ${this.drafts[file.name] !== this.baselines[file.name] && file.name in this.baselines ? b`<tui-text variant="warning">unsaved</tui-text>` : ""}
                ${file.protected ? "protected" : ""}
                ${!file.protected ? b`<tui-button
                        variant="error"
                        ?disabled=${this.running}
                        @click=${() => this.deleteFile(file)}
                        >Delete</tui-button
                      >` : ""}
              </div>
            `)}
        </tui-box>
        <section style="flex: 4 1 60ch; min-width: 0">
          <div>
            ${this.activeFile ?? "No file selected"}
            ${active?.protected ? "│ protected" : ""}
            ${dirty ? b`│ <tui-text variant="warning">unsaved</tui-text>` : ""}
            <label
              >Scheme&nbsp;<tui-select
                aria-label="Code editor color scheme"
                value=${this.editorColorScheme}
                @change=${(event) => this.setEditorColorScheme(event.currentTarget.value)}
              >
                <option value="monochrome">Monochrome</option>
                <option value="latte">Latte</option>
                <option value="frappe">Frappé</option>
                <option value="macchiato">Macchiato</option>
                <option value="mocha">Mocha</option>
              </tui-select></label
            >
            <tui-button
              ?disabled=${!dirty || this.running || this.busyAction !== ""}
              @click=${this.saveFile}
              >Save</tui-button
            >
          </div>
          <sentinel-code-editor
            aria-label="${this.activeFile ?? "Task file"} content"
            document-id="${this.selectedId ?? ""}/${this.activeFile ?? ""}"
            filename=${this.activeFile ?? "file.txt"}
            language=${active?.language ?? "plaintext"}
            color-scheme=${this.editorColorScheme}
            .value=${draft}
            ?disabled=${!this.activeFile || this.running}
            @input=${(event) => this.updateDraft(event.currentTarget.value)}
          ></sentinel-code-editor>
        </section>
      </tui-flex>
    `;
	}
	renderSchedule() {
		const parts = this.intervalParts();
		return b`
      <div>Schedule</div>
      <tui-radio-buttonset
        aria-label="Task schedule mode"
        value=${this.scheduleMode}
        ?disabled=${this.running}
        @change=${(event) => this.setScheduleMode(event.currentTarget.value)}
      >
        <tui-radio-button value="off">Off</tui-radio-button>
        <tui-radio-button value="cron">Cron</tui-radio-button>
        <tui-radio-button value="interval">Interval</tui-radio-button>
      </tui-radio-buttonset>
      ${this.scheduleMode === "cron" ? b`
              <div>
                <label
                  >Cron&nbsp;<tui-input
                    value=${this.metadata.schedule ?? defaultCron}
                    size="24"
                    ?disabled=${this.running}
                    @input=${(event) => this.patchMetadata({ schedule: event.currentTarget.value || defaultCron })}
                  ></tui-input
                ></label>
              </div>
              ${cronFields.map((field) => {
			const selected = this.cronValues(field.index);
			return b`
                  <div>${field.label}</div>
                  <tui-flex align="baseline" wrap>
                    ${field.options.map(([value, label]) => b`
                        <tui-toggle
                          ?checked=${selected.has(value)}
                          ?disabled=${this.running}
                          @change=${(event) => this.toggleCronValue(field.index, value, event.currentTarget.checked)}
                          >${value} ${label}</tui-toggle
                        ><span aria-hidden="true">&nbsp;</span>
                      `)}
                  </tui-flex>
                `;
		})}
            ` : ""}
      ${this.scheduleMode === "interval" ? b`
              <tui-flex align="baseline" wrap>
                <label
                  >Days&nbsp;<tui-input
                    type="number"
                    min="0"
                    value=${parts.days}
                    @change=${(event) => this.patchInterval("days", event.currentTarget.value)}
                  ></tui-input
                ></label>
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Hours&nbsp;<tui-input
                    type="number"
                    min="0"
                    max="23"
                    value=${parts.hours}
                    @change=${(event) => this.patchInterval("hours", event.currentTarget.value)}
                  ></tui-input
                ></label>
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Minutes&nbsp;<tui-input
                    type="number"
                    min="0"
                    max="59"
                    value=${parts.minutes}
                    @change=${(event) => this.patchInterval("minutes", event.currentTarget.value)}
                  ></tui-input
                ></label>
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Run when&nbsp;<tui-select
                    value=${this.metadata.schedulePolicy?.runWhen ?? "idle"}
                    @change=${(event) => this.patchSchedulePolicy({ runWhen: event.currentTarget.value })}
                  >
                    <option value="idle">Idle</option>
                    <option value="immediate">Immediate</option>
                  </tui-select></label
                >
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Priority&nbsp;<tui-input
                    type="number"
                    min="-1000"
                    max="1000"
                    value=${this.metadata.schedulePolicy?.priority ?? 0}
                    @change=${(event) => this.patchSchedulePolicy({ priority: Number(event.currentTarget.value) })}
                  ></tui-input
                ></label>
              </tui-flex>
            ` : ""}
    `;
	}
	renderMetadata() {
		if (!this.metadata) return b`<div>Loading metadata…</div>`;
		return b`
      <tui-flex align="baseline" justify="between" wrap>
        <span>Metadata</span>
        <tui-button
          ?disabled=${!this.metadataDirty || this.running || this.busyAction !== ""}
          @click=${this.saveMetadata}
          >Save</tui-button
        >
      </tui-flex>
      <div>
        <label
          ><span>Name</span>
          <tui-input
            block
            value=${this.metadata.name}
            @input=${(event) => this.patchMetadata({ name: event.currentTarget.value })}
          ></tui-input
        ></label>
        <tui-toggle
          ?checked=${this.metadata.enabled}
          ?disabled=${this.running}
          @change=${(event) => this.patchMetadata({ enabled: event.currentTarget.checked })}
          >Enabled</tui-toggle
        >
      </div>
      <div>
        <label>Description</label>
        <tui-textarea
          aria-label="Task description"
          block
          rows="4"
          value=${this.metadata.description}
          ?disabled=${this.running}
          @input=${(event) => this.patchMetadata({ description: event.currentTarget.value })}
        ></tui-textarea>
      </div>
      <div>
        <label
          ><span>Tags</span>
          <tui-input
            block
            value=${this.metadata.tags.join(", ")}
            ?disabled=${this.running}
            @input=${(event) => this.patchMetadata({ tags: event.currentTarget.value.split(",").map((tag) => tag.trim()).filter(Boolean) })}
          ></tui-input
        ></label>
      </div>
      <div>
        <label
          >Timeout (seconds)&nbsp;<tui-input
            type="number"
            min="0"
            step="60"
            value=${this.metadata.timeout}
            ?disabled=${this.running}
            @change=${(event) => this.patchMetadata({ timeout: Number(event.currentTarget.value) })}
          ></tui-input
        ></label>
      </div>
      <div>
        <label
          ><span>Working directory</span>
          <tui-input
            block
            value=${this.metadata.cwd}
            placeholder="@/tasks/artifacts/{{task-id}}"
            ?disabled=${this.running}
            @input=${(event) => this.patchMetadata({ cwd: event.currentTarget.value })}
          ></tui-input
        ></label>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderSchedule()}
    `;
	}
	renderRun() {
		return b`
      <tui-box heading="Run" border="single">
        <div>
          Status
          <tui-text variant=${statusVariant(this.run?.status) || ""}
            >${this.run?.status ?? "idle"}</tui-text
          >
        </div>
        <div>History</div>
        ${this.runs.length ? this.runs.map((run) => b`
                  <div>
                    <span aria-hidden="true"
                      >${run.id === this.runId ? "▶" : " "}&nbsp;</span
                    ><tui-button @click=${() => this.loadRun(run.id)}
                      >${run.status} -
                      ${run.createdAt ? formatDateTime(run.createdAt) : run.id}</tui-button
                    >
                  </div>
                `) : "No runs"}
        <div>Inputs (JSON)</div>
        <tui-textarea
          aria-label="Task run inputs"
          block
          rows="4"
          value=${this.runInputs}
          ?disabled=${this.running}
          @input=${(event) => this.runInputs = event.currentTarget.value}
        ></tui-textarea>
        <div>Log</div>
        ${(this.run?.log ?? []).map((line) => b`<div><code>${line}</code></div>`)}
        ${this.run?.error ? b`<tui-text variant="error">${this.run.error}</tui-text>` : ""}
        <pre style="white-space: pre-wrap; overflow-wrap: anywhere">
${this.run?.liveOutput ?? " "}</pre>
      </tui-box>
    `;
	}
	renderWorkbench() {
		if (this.loading && !this.task) return b`<div>Loading task…</div>`;
		if (!this.task) return b`<div>No task selected</div>`;
		return b`
      ${this.renderToolbar()}
      ${this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError ? b`<tui-text variant="error">${this.actionError}</tui-text>` : ""}
      <div aria-hidden="true">&nbsp;</div>
      <tui-flex align="start" wrap>
        <section style="flex: 3 1 60ch; min-width: 0">
          <tui-radio-buttonset
            aria-label="Task editor view"
            value=${this.tab}
            @change=${(event) => this.tab = event.currentTarget.value}
          >
            <tui-radio-button value="files">Files</tui-radio-button>
            <tui-radio-button value="metadata">Metadata</tui-radio-button>
          </tui-radio-buttonset>
          ${this.tab === "metadata" ? this.renderMetadata() : this.renderFiles()}
        </section>
        <aside style="flex: 1 1 32ch; min-width: 0">${this.renderRun()}</aside>
      </tui-flex>
    `;
	}
	render() {
		return b`
      <tui-flex align="baseline" justify="between" wrap>
        <span>${this.tasks.length} core and user task definitions</span>
        <span>
          <tui-button
            ?disabled=${this.busyAction !== ""}
            @click=${this.createTask}
            >New</tui-button
          >
          <tui-button @click=${() => this.loadTasks()}>Refresh</tui-button>
        </span>
      </tui-flex>
      <div aria-hidden="true">&nbsp;</div>
      ${this.loading && this.tasks.length === 0 ? b`<div>Loading tasks…</div>` : b`
              <tui-flex align="start" wrap>
                <aside style="flex: 1 1 24ch; min-width: 0">
                  ${this.renderTaskList()}
                </aside>
                <section style="flex: 4 1 70ch; min-width: 0">
                  ${this.renderWorkbench()}
                </section>
              </tui-flex>
            `}
    `;
	}
};
customElements.define("sentinel-tasks", SentinelTasks);
//#endregion
//#region src/sentinel-research.js
var SentinelResearch = class extends i {
	static properties = {
		tab: { state: true },
		kind: { state: true },
		staleOnly: { state: true },
		ratingSymbol: { state: true },
		busy: { state: true },
		notice: { state: true },
		actionError: { state: true },
		artifactUnit: { state: true },
		activeArtifact: { state: true },
		artifactContent: { state: true },
		artifactLoading: { state: true },
		artifactError: { state: true }
	};
	constructor() {
		super();
		this.tab = "status";
		this.kind = "";
		this.staleOnly = false;
		this.ratingSymbol = "";
		this.busy = false;
		this.notice = "";
		this.actionError = "";
		this.artifactUnit = void 0;
		this.activeArtifact = "";
		this.artifactContent = "";
		this.artifactLoading = false;
		this.artifactError = "";
	}
	status = new LiveResource(this, (signal) => getJson("/api/ai/status", { signal }), { interval: 3e3 });
	units = new LiveResource(this, (signal) => getJson(this.unitsPath, { signal }), { interval: 1e4 });
	allUnits = new LiveResource(this, (signal) => getJson("/api/ai/units", { signal }), { interval: 1e4 });
	history = new LiveResource(this, (signal) => getJson("/api/ai/history?limit=100", { signal }), { interval: 1e4 });
	createRenderRoot() {
		return this;
	}
	get unitsPath() {
		const parameters = new URLSearchParams();
		if (this.kind) parameters.set("kind", this.kind);
		if (this.staleOnly) parameters.set("stale_only", "true");
		const query = parameters.toString();
		return `/api/ai/units${query ? `?${query}` : ""}`;
	}
	changeUnitsFilter(name, value) {
		this[name] = value;
		this.units.refresh();
	}
	changeTab(event) {
		const nextTab = event.currentTarget.value;
		if (this.tab === "tasks" && nextTab !== "tasks") {
			const tasks = this.querySelector("sentinel-tasks");
			if (tasks?.confirmClose && !tasks.confirmClose()) {
				event.currentTarget.value = "tasks";
				return;
			}
		}
		this.tab = nextTab;
	}
	async refreshAll() {
		await Promise.all([
			this.status.refresh(),
			this.units.refresh(),
			this.allUnits.refresh(),
			this.history.refresh()
		]);
	}
	async requestResearch(kind, unitKind, unitKey) {
		this.busy = true;
		this.notice = "";
		this.actionError = "";
		try {
			await postJson("/api/ai/requests", {
				kind,
				unit_kind: unitKind,
				unit_key: unitKey
			});
			this.notice = `${kind === "rate" ? "Rating" : "Analysis"} queued for ${unitKey}`;
			await this.refreshAll();
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busy = false;
		}
	}
	async openArtifacts(unit) {
		this.artifactUnit = unit;
		this.activeArtifact = unit.artifacts?.[0] ?? "";
		this.artifactContent = "";
		this.artifactError = "";
		if (this.activeArtifact) await this.loadArtifact();
	}
	closeArtifacts() {
		this.artifactUnit = void 0;
		this.activeArtifact = "";
		this.artifactContent = "";
	}
	async changeArtifact(name) {
		this.activeArtifact = name;
		await this.loadArtifact();
	}
	async loadArtifact() {
		const unit = this.artifactUnit;
		const name = this.activeArtifact;
		if (!unit || !name) return;
		this.artifactLoading = true;
		this.artifactError = "";
		try {
			let content = (await getJson(`/api/ai/artifacts/${encodeURIComponent(unit.kind)}/${encodeURIComponent(unit.key)}/${encodeURIComponent(name)}`)).content ?? "";
			if (name.endsWith(".json")) try {
				content = JSON.stringify(JSON.parse(content), null, 2);
			} catch {}
			this.artifactContent = content;
		} catch (error) {
			this.artifactError = error.message;
		} finally {
			this.artifactLoading = false;
		}
	}
	renderStatus() {
		const status = this.status.value;
		const security = status.staleness?.security ?? {
			stale: 0,
			total: 0
		};
		const securities = (this.allUnits.value?.units ?? []).filter((unit) => unit.kind === "security");
		return b`
      <div>
        Securities ${security.stale}/${security.total} stale │ Queued
        ${status.queued?.length ?? 0} │ Memory ${status.memory?.findings ?? "-"}
        findings
      </div>
      <div aria-hidden="true">&nbsp;</div>
      <tui-box heading="Current Work" border="single">
        ${status.running ? b`
                <div>${status.running.label}</div>
                <div>${status.running.kind}:${status.running.key}</div>
                ${status.running.elapsed_seconds !== void 0 ? b`<div>
                        ${formatDuration(status.running.elapsed_seconds * 1e3)}
                      </div>` : ""}
              ` : "Idle"}
      </tui-box>
      <div aria-hidden="true">&nbsp;</div>
      <tui-flex align="start" wrap>
        <tui-box
          heading="Next in Line"
          border="single"
          style="flex: 1 1 40ch; min-width: 0"
        >
          ${status.queued?.length ? status.queued.map((item) => b`
                    <div>
                      ${item.unit_label ?? `${item.unit_kind}:${item.unit_key}`}
                      │ ${item.task_name ?? item.task_id ?? item.kind}
                    </div>
                  `) : "Queue empty"}
        </tui-box>
        <tui-box
          heading="Latest Tick"
          border="single"
          style="flex: 1 1 40ch; min-width: 0"
        >
          ${status.last_run ? b`
                  <div>
                    <tui-text
                      variant=${statusVariant(status.last_run.status) || ""}
                      >${status.last_run.status}</tui-text
                    >
                    │ ${formatRelativeTime(status.last_run.finished_at)}
                  </div>
                  ${status.last_run.unit_label ? b`<div>
                          ${status.last_run.unit_label}
                          ${status.last_run.unit_key ? `(${status.last_run.unit_key})` : ""}
                        </div>` : ""}
                  ${status.last_run.duration_seconds !== void 0 ? b`<div>
                          ${formatDuration(status.last_run.duration_seconds * 1e3)}
                        </div>` : ""}
                  ${status.last_run.error ? b`<tui-text variant="error"
                          >${status.last_run.error}</tui-text
                        >` : ""}
                ` : "No runs yet"}
        </tui-box>
      </tui-flex>
      ${status.staleness?.most_stale ? b`<div>
              Oldest: ${status.staleness.most_stale.label}
              (${status.staleness.most_stale.kind})
            </div>` : ""}
      ${status.memory?.error ? b`<tui-text variant="error"
              >Memory: ${status.memory.error}</tui-text
            >` : ""}
      <div aria-hidden="true">&nbsp;</div>
      <tui-box heading="Manual Rating" border="single">
        <tui-flex align="baseline" wrap>
          <label
            >Security&nbsp;<tui-select
              value=${this.ratingSymbol}
              @change=${(event) => this.ratingSymbol = event.currentTarget.value}
            >
              <option value="">Select a security</option>
              ${securities.map((unit) => b`<option value=${unit.key}>
                    ${unit.label} (${unit.key})
                  </option>`)}
            </tui-select></label
          >
          <span aria-hidden="true">&nbsp;</span>
          <tui-button
            ?disabled=${!this.ratingSymbol || this.busy}
            @click=${() => this.requestResearch("rate", "security", this.ratingSymbol)}
            >Rate now</tui-button
          >
        </tui-flex>
      </tui-box>
    `;
	}
	renderUnits() {
		const units = this.units.value?.units ?? [];
		return b`
      <tui-flex align="baseline" wrap>
        <label
          >Kind&nbsp;<tui-select
            value=${this.kind}
            @change=${(event) => this.changeUnitsFilter("kind", event.currentTarget.value)}
          >
            <option value="">All units</option>
            <option value="security">Securities</option>
            <option value="portfolio">Portfolio</option>
          </tui-select></label
        >
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-toggle
          ?checked=${this.staleOnly}
          @change=${(event) => this.changeUnitsFilter("staleOnly", event.currentTarget.checked)}
          >Stale only</tui-toggle
        >
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-button @click=${this.refreshAll}>Refresh</tui-button>
      </tui-flex>
      <div aria-hidden="true">&nbsp;</div>
      ${this.units.loading && !this.units.value ? "Loading units…" : units.length === 0 ? "No research units match this view." : b`
                <div style="overflow: auto; min-width: 0">
                  <table style="border-collapse: collapse; width: 100%">
                    <thead>
                      <tr>
                        <th style="text-align: left">Unit</th>
                        <th style="text-align: left">│ Kind</th>
                        <th style="text-align: left">│ Last analyzed</th>
                        <th style="text-align: left">│ State</th>
                        <th style="text-align: left">│ Error</th>
                        <th style="text-align: left">│ Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${units.map((unit) => {
			const state = unit.status === "running" ? "running" : unit.stale ? "stale" : "fresh";
			return b`
                          <tr>
                            <td style="text-align: left; vertical-align: top">
                              ${unit.label}<br />${unit.key}
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │ ${unit.kind}
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │
                              ${unit.last_analyzed_at ? formatRelativeTime(unit.last_analyzed_at) : "Never"}
                            </td>
                            <td style="text-align: left; vertical-align: top">
                              │
                              <tui-text variant=${statusVariant(state) || ""}
                                >${state}</tui-text
                              >
                            </td>
                            <td
                              style="text-align: left; vertical-align: top; max-width: 40ch; overflow-wrap: anywhere"
                            >
                              │ ${unit.last_error ?? "-"}
                            </td>
                            <td
                              style="text-align: left; vertical-align: top; white-space: nowrap"
                            >
                              │
                              ${unit.kind !== "portfolio" ? b`<tui-button
                                      ?disabled=${this.busy || unit.status === "running"}
                                      @click=${() => this.requestResearch("analyze", unit.kind, unit.key)}
                                      >Analyze</tui-button
                                    >` : ""}
                              <tui-button
                                ?disabled=${!unit.artifacts?.length}
                                @click=${() => this.openArtifacts(unit)}
                                >View</tui-button
                              >
                            </td>
                          </tr>
                        `;
		})}
                    </tbody>
                  </table>
                </div>
              `}
    `;
	}
	renderHistory() {
		const history = this.history.value?.history ?? [];
		if (this.history.loading && !this.history.value) return b`<div>Loading pipeline history…</div>`;
		if (history.length === 0) return b`<div>No pipeline runs yet.</div>`;
		return b`
      <div style="overflow: auto; min-width: 0">
        <table style="border-collapse: collapse; width: 100%">
          <thead>
            <tr>
              <th style="text-align: left">Unit</th>
              <th style="text-align: left">│ Status</th>
              <th style="text-align: left">│ Duration</th>
              <th style="text-align: left">│ Finished</th>
              <th style="text-align: left">│ Error</th>
            </tr>
          </thead>
          <tbody>
            ${history.map((entry) => b`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${entry.unit_label ?? entry.unit_key ?? entry.job_id?.replace("ai:tick:", "") ?? "-"}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │
                    <tui-text variant=${statusVariant(entry.status) || ""}
                      >${entry.status}</tui-text
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatDuration(entry.duration_ms)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │
                    ${formatRelativeTime(typeof entry.executed_at === "number" ? entry.executed_at * 1e3 : entry.executed_at)}
                  </td>
                  <td
                    style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
                  >
                    │ ${entry.error ?? "-"}
                  </td>
                </tr>
              `)}
          </tbody>
        </table>
      </div>
    `;
	}
	renderArtifactModal() {
		const unit = this.artifactUnit;
		if (!unit) return "";
		return b`
      <tui-modal
        heading="${unit.label} / artifacts"
        open
        @close=${this.closeArtifacts}
      >
        ${unit.artifacts?.length ? b`
                <label
                  >Artifact&nbsp;<tui-select
                    value=${this.activeArtifact}
                    @change=${(event) => this.changeArtifact(event.currentTarget.value)}
                  >
                    ${unit.artifacts.map((name) => b`<option value=${name}>${name}</option>`)}
                  </tui-select></label
                >
                <div aria-hidden="true">&nbsp;</div>
                ${this.artifactLoading ? "Loading artifact…" : this.artifactError ? b`<tui-text variant="error"
                          >${this.artifactError}</tui-text
                        >` : b`<pre
                          style="white-space: pre-wrap; overflow-wrap: anywhere"
                        >
${this.artifactContent}</pre>`}
              ` : "No artifacts have been written for this unit."}
      </tui-modal>
    `;
	}
	render() {
		const error = this.status.error ?? this.units.error ?? this.allUnits.error ?? this.history.error;
		const loading = !this.status.value && this.status.loading || !this.allUnits.value && this.allUnits.loading;
		const enabled = this.status.value?.enabled;
		const pipelineState = loading ? b`<tui-text>loading</tui-text>` : error && !this.status.value ? b`<tui-text variant="error">unavailable</tui-text>` : b`<tui-text variant=${enabled ? "success" : ""}
            >${enabled ? "enabled" : "paused"}</tui-text
          >`;
		let content;
		if (this.tab === "tasks") content = b`<sentinel-tasks></sentinel-tasks>`;
		else if (loading) content = b`<div>Loading research pipeline…</div>`;
		else if (error && !this.status.value) content = b`<tui-text variant="error">${error.message}</tui-text>`;
		else if (this.tab === "units") content = this.renderUnits();
		else if (this.tab === "history") content = this.renderHistory();
		else content = this.renderStatus();
		return b`
      <div>Pipeline ${pipelineState}</div>
      <tui-radio-buttonset
        aria-label="Research pipeline view"
        value=${this.tab}
        @change=${this.changeTab}
      >
        <tui-radio-button value="status">Status</tui-radio-button>
        <tui-radio-button value="units">Units</tui-radio-button>
        <tui-radio-button value="history">History</tui-radio-button>
        <tui-radio-button value="tasks">Tasks</tui-radio-button>
      </tui-radio-buttonset>
      <div aria-hidden="true">&nbsp;</div>
      ${content}
      ${this.tab !== "tasks" && this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.tab !== "tasks" && this.actionError ? b`<tui-text variant="error">${this.actionError}</tui-text>` : ""}
      ${this.renderArtifactModal()}
    `;
	}
};
customElements.define("sentinel-research", SentinelResearch);
//#endregion
//#region src/sentinel-scheduler.js
var intervalMultipliers = {
	minutes: 1,
	hours: 60,
	days: 1440
};
function displayInterval(minutes) {
	if (minutes >= 1440 && minutes % 1440 === 0) return {
		value: minutes / 1440,
		unit: "days"
	};
	if (minutes >= 60 && minutes % 60 === 0) return {
		value: minutes / 60,
		unit: "hours"
	};
	return {
		value: minutes,
		unit: "minutes"
	};
}
var SentinelScheduler = class extends i {
	static properties = {
		tab: { state: true },
		busyAction: { state: true },
		actionError: { state: true },
		notice: { state: true }
	};
	constructor() {
		super();
		this.tab = "status";
		this.busyAction = "";
		this.actionError = "";
		this.notice = "";
	}
	schedules = new LiveResource(this, (signal) => getJson("/api/jobs/schedules", { signal }), { interval: 5e3 });
	status = new LiveResource(this, (signal) => getJson("/api/jobs", { signal }), { interval: 3e3 });
	history = new LiveResource(this, (signal) => getJson("/api/jobs/history?limit=100", { signal }), { interval: 1e4 });
	createRenderRoot() {
		return this;
	}
	async updateSchedule(jobType, values) {
		this.busyAction = `update:${jobType}`;
		this.actionError = "";
		this.notice = "";
		try {
			await putJson(`/api/jobs/schedules/${encodeURIComponent(jobType)}`, values);
			this.notice = `${jobType} updated`;
			await this.schedules.refresh();
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async runJob(jobType) {
		this.busyAction = `run:${jobType}`;
		this.actionError = "";
		this.notice = "";
		try {
			await postJson(`/api/jobs/${encodeURIComponent(jobType)}/run`);
			this.notice = `${jobType} started`;
			await Promise.all([
				this.status.refresh(),
				this.schedules.refresh(),
				this.history.refresh()
			]);
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	updateInterval(job, field, value, unit) {
		const minutes = Math.round(Number(value) * intervalMultipliers[unit]);
		if (minutes > 0) this.updateSchedule(job.job_type, { [field]: minutes });
	}
	renderInterval(job, field, label) {
		const display = displayInterval(Number(job[field] ?? job.interval_minutes));
		return b`
      <label
        >${label}&nbsp;<tui-input
          type="number"
          min="1"
          max="10080"
          value=${display.value}
          ?disabled=${this.busyAction !== ""}
          @change=${(event) => this.updateInterval(job, field, event.currentTarget.value, display.unit)}
        ></tui-input
      ></label>
      <tui-select
        aria-label="${label} unit for ${job.job_type}"
        value=${display.unit}
        ?disabled=${this.busyAction !== ""}
        @change=${(event) => this.updateInterval(job, field, display.value, event.currentTarget.value)}
      >
        <option value="minutes">Minutes</option>
        <option value="hours">Hours</option>
        <option value="days">Days</option>
      </tui-select>
    `;
	}
	renderStatus() {
		const status = this.status.value ?? {};
		return b`
      <tui-box heading="Currently Running" border="single">
        ${status.current ?? "No job running"}
      </tui-box>
      <div aria-hidden="true">&nbsp;</div>
      <tui-box heading="Upcoming Jobs" border="single">
        ${status.upcoming?.length ? status.upcoming.map((job) => b`
                  <div>
                    ${job.job_type} │ ${formatRelativeTime(job.next_run)}
                  </div>
                `) : "No upcoming jobs"}
      </tui-box>
      <div aria-hidden="true">&nbsp;</div>
      <tui-box heading="Recent Jobs" border="single">
        ${status.recent?.length ? status.recent.map((job) => b`
                  <div>
                    ${job.job_type} │
                    <tui-text variant=${statusVariant(job.status) || ""}
                      >${job.status}</tui-text
                    >
                    │ ${formatRelativeTime(job.executed_at)}
                  </div>
                `) : "No recent jobs"}
      </tui-box>
    `;
	}
	renderJob(job) {
		const busy = this.busyAction !== "";
		return b`
      <div>
        <tui-flex align="baseline" justify="between" wrap>
          <span>
            ${job.job_type}
            ${job.last_status ? b`<tui-text variant=${statusVariant(job.last_status) || ""}
                    >${job.last_status}</tui-text
                  >` : ""}
          </span>
          <span>
            <label
              >Timing&nbsp;<tui-select
                value=${String(job.market_timing)}
                ?disabled=${busy}
                @change=${(event) => this.updateSchedule(job.job_type, { market_timing: Number(event.currentTarget.value) })}
              >
                <option value="0">Any time</option>
                <option value="1">After close</option>
                <option value="2">During open</option>
                <option value="3">All closed</option>
              </tui-select></label
            >
            <tui-button
              ?disabled=${busy}
              @click=${() => this.runJob(job.job_type)}
              >${this.busyAction === `run:${job.job_type}` ? "Running…" : "Run"}</tui-button
            >
          </span>
        </tui-flex>
        <div>${job.description ?? ""}</div>
        <tui-flex align="baseline" wrap>
          ${this.renderInterval(job, "interval_minutes", "Interval")}
          <span aria-hidden="true">&nbsp;│&nbsp;</span>
          ${this.renderInterval(job, "interval_market_open_minutes", "Market open")}
          ${job.next_run ? b`<span aria-hidden="true">&nbsp;│&nbsp;</span
                  ><span>Next ${formatRelativeTime(job.next_run)}</span>` : ""}
        </tui-flex>
      </div>
    `;
	}
	renderJobs() {
		const schedules = this.schedules.value?.schedules ?? [];
		return [...new Set(schedules.map((job) => job.category).filter(Boolean))].map((category, index) => b`
        ${index > 0 ? b`<div aria-hidden="true">&nbsp;</div>` : ""}
        <tui-box heading=${category} border="single">
          ${schedules.filter((job) => job.category === category).map((job, jobIndex) => b`
                ${jobIndex > 0 ? b`<div aria-hidden="true">────────────────</div>` : ""}
                ${this.renderJob(job)}
              `)}
        </tui-box>
      `);
	}
	renderHistory() {
		const history = this.history.value?.history ?? [];
		if (history.length === 0) return b`<div>No execution history</div>`;
		return b`
      <div style="overflow: auto; min-width: 0">
        <table style="border-collapse: collapse; width: 100%">
          <thead>
            <tr>
              <th style="text-align: left">Job ID</th>
              <th style="text-align: left">│ Status</th>
              <th style="text-align: left">│ Duration</th>
              <th style="text-align: left">│ Executed</th>
              <th style="text-align: left">│ Error</th>
            </tr>
          </thead>
          <tbody>
            ${history.map((entry) => b`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${entry.job_id}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │
                    <tui-text variant=${statusVariant(entry.status) || ""}
                      >${entry.status}</tui-text
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatDuration(entry.duration_ms)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatDateTime(entry.executed_at, { seconds: true })}
                  </td>
                  <td
                    style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
                  >
                    │ ${entry.error ?? "-"}
                  </td>
                </tr>
              `)}
          </tbody>
        </table>
      </div>
    `;
	}
	render() {
		const error = this.schedules.error ?? this.status.error ?? this.history.error;
		if (!this.schedules.value && this.schedules.loading || !this.status.value && this.status.loading || !this.history.value && this.history.loading) return b`<div>Loading scheduler…</div>`;
		if (error) return b`<tui-text variant="error"
        >Error loading scheduler: ${error.message}</tui-text
      >`;
		return b`
      <tui-radio-buttonset
        aria-label="Scheduler view"
        value=${this.tab}
        @change=${(event) => this.tab = event.currentTarget.value}
      >
        <tui-radio-button value="status">Status</tui-radio-button>
        <tui-radio-button value="jobs">Jobs</tui-radio-button>
        <tui-radio-button value="history">History</tui-radio-button>
      </tui-radio-buttonset>
      <div aria-hidden="true">&nbsp;</div>
      ${this.tab === "jobs" ? this.renderJobs() : this.tab === "history" ? this.renderHistory() : this.renderStatus()}
      ${this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError ? b`<tui-text variant="error">${this.actionError}</tui-text>` : ""}
    `;
	}
};
customElements.define("sentinel-scheduler", SentinelScheduler);
//#endregion
//#region src/sentinel-settings.js
var tradingFields = [
	{
		key: "trading_mode",
		label: "Trading Mode",
		description: "Research mode simulates trades without executing",
		type: "select",
		default: "research",
		options: [["research", "Research (Paper Trading)"], ["live", "Live Trading"]]
	},
	{
		key: "max_position_pct",
		label: "Max Position %",
		description: "Maximum allocation to a single security",
		type: "number",
		default: 20,
		min: 5,
		max: 100
	},
	{
		key: "min_position_pct",
		label: "Min Position %",
		description: "Minimum allocation to maintain a position",
		type: "number",
		default: 2,
		min: .5,
		max: 20,
		step: .5
	},
	{
		key: "target_cash_pct",
		label: "Target Cash %",
		description: "Target cash allocation in portfolio",
		type: "number",
		default: 0,
		min: 0,
		max: 50
	},
	{
		key: "min_cash_buffer",
		label: "Min Cash Buffer %",
		description: "Minimum cash to keep as safety buffer",
		type: "number",
		default: .005,
		min: 0,
		max: 10,
		step: .01,
		scale: 100
	},
	{
		key: "min_trade_value",
		label: "Min Trade Value (EUR)",
		description: "Minimum trade value in EUR",
		type: "number",
		default: 100,
		min: 10,
		max: 1e4
	}
];
var feeFields = [{
	key: "transaction_fee_fixed",
	label: "Fixed Transaction Fee (EUR)",
	description: "Fixed fee per trade",
	type: "number",
	default: 2,
	min: 0,
	max: 50,
	step: .01
}, {
	key: "transaction_fee_percent",
	label: "Variable Transaction Fee %",
	description: "Fee as percentage of trade value",
	type: "number",
	default: .2,
	min: 0,
	max: 5,
	step: .01
}];
var strategyDraftFields = [
	[
		"strategy_min_opp_score",
		"Minimum Opportunity Score",
		.55,
		0,
		1,
		.001,
		"Minimum opp score required to enter opportunity sleeve"
	],
	[
		"strategy_ideal_qualifying_threshold",
		"Ideal Qualification Threshold",
		.65,
		0,
		1,
		.001,
		"Minimum AI research multiplier required for an ideal target"
	],
	[
		"strategy_core_timing_min_score",
		"Core Timing Score",
		.3,
		0,
		1,
		.001,
		"Minimum opportunity score for a normally timed core buy"
	],
	[
		"strategy_core_timing_min_dip_score",
		"Core Timing Dip",
		.2,
		0,
		1,
		.001,
		"Minimum dip score for a normally timed core buy"
	],
	[
		"strategy_fallback_wait_days",
		"Fallback Wait",
		30,
		0,
		365,
		1,
		"Days without an executable opportunity before one convergence buy"
	],
	[
		"strategy_entry_t1_dd",
		"Entry T1 Drawdown",
		-.1,
		-.9,
		0,
		.001,
		"First opportunity tranche threshold (dd252)"
	],
	[
		"strategy_entry_t2_dd",
		"Entry T2 Drawdown",
		-.16,
		-.9,
		0,
		.001,
		"Second opportunity tranche threshold (dd252)"
	],
	[
		"strategy_entry_t3_dd",
		"Entry T3 Drawdown",
		-.22,
		-.9,
		0,
		.001,
		"Third opportunity tranche threshold (dd252)"
	],
	[
		"strategy_entry_memory_days",
		"Entry Memory Days",
		45,
		1,
		252,
		1,
		"Keep recent-dip memory active for post-turn entries"
	],
	[
		"strategy_memory_max_boost",
		"Memory Max Boost",
		.12,
		0,
		.5,
		.001,
		"Maximum boost added to opp score from recent dip memory"
	],
	[
		"strategy_opportunity_addon_threshold",
		"Opportunity Add-On Threshold",
		.75,
		0,
		1,
		.001,
		"Allow add-on buys for held opportunity names above this score"
	],
	[
		"strategy_max_opportunity_buys_per_cycle",
		"Max Opportunity Buys / Cycle",
		1,
		0,
		50,
		1,
		"Hard cap on total opportunity buys per rebalance cycle"
	],
	[
		"strategy_max_new_opportunity_buys_per_cycle",
		"Max New Opportunity Buys / Cycle",
		1,
		0,
		50,
		1,
		"Hard cap on opening new opportunity positions per cycle"
	]
].map(([key, label, defaultValue, min, max, step, description]) => ({
	key,
	label,
	default: defaultValue,
	min,
	max,
	step,
	description,
	type: "number"
}));
var strategyFields = [
	[
		"rebalance_threshold_pct",
		"Rebalance Threshold %",
		5,
		1,
		20,
		1,
		"Minimum deviation to trigger rebalance"
	],
	[
		"strategy_lot_standard_max_pct",
		"Standard Lot Max %",
		.08,
		0,
		100,
		.01,
		"Max ticket size treated as standard lot class",
		100
	],
	[
		"strategy_lot_coarse_max_pct",
		"Coarse Lot Max %",
		.3,
		0,
		100,
		.01,
		"Max ticket size treated as coarse lot class",
		100
	],
	[
		"strategy_coarse_max_new_lots_per_cycle",
		"Coarse Max New Lots",
		1,
		1,
		10,
		1,
		"Max new coarse lots per rebalance cycle"
	],
	[
		"strategy_opportunity_cooloff_days",
		"Opportunity Cool-Off Days",
		7,
		0,
		365,
		1,
		"Minimum days between opposite actions for opportunity sleeve"
	],
	[
		"strategy_core_cooloff_days",
		"Core Cool-Off Days",
		21,
		0,
		365,
		1,
		"Minimum days between opposite actions for core sleeve"
	],
	[
		"strategy_same_side_cooloff_days",
		"Same-Side Cool-Off Days",
		15,
		0,
		365,
		1,
		"Minimum days between same-side actions"
	],
	[
		"strategy_rotation_time_stop_days",
		"Rotation Time-Stop Days",
		90,
		1,
		365,
		1,
		"Exit opportunity positions if the thesis stalls beyond this horizon"
	]
].map(([key, label, defaultValue, min, max, step, description, scale]) => ({
	key,
	label,
	default: defaultValue,
	min,
	max,
	step,
	description,
	scale,
	type: "number"
}));
var forecastFields = [
	{
		key: "forecasting_enabled",
		label: "Forecast timing",
		description: "Use stored forecasts as a bounded opportunity-score modifier",
		type: "toggle",
		default: true
	},
	{
		key: "forecasting_service_url",
		label: "Forecasting Service URL",
		type: "text",
		default: "http://127.0.0.1:8010"
	},
	{
		key: "forecasting_provider",
		label: "Provider",
		type: "select",
		default: "toto2",
		options: [["toto2", "Toto 2.0"], ["naive", "Naive local test provider"]]
	},
	{
		key: "forecasting_model_id",
		label: "Model ID",
		type: "text",
		default: "Datadog/Toto-2.0-1B"
	},
	{
		key: "forecasting_horizon_weeks",
		label: "Horizon (weeks)",
		description: "Forecast horizon in weekly steps",
		type: "number",
		default: 4,
		min: 1,
		max: 52
	},
	{
		key: "forecasting_context_weeks",
		label: "Context (weeks)",
		description: "Maximum weekly return history sent to the model",
		type: "number",
		default: 520,
		min: 104,
		max: 1040
	},
	{
		key: "forecasting_min_history_weeks",
		label: "Minimum History (weeks)",
		type: "number",
		default: 104,
		min: 52,
		max: 520
	},
	{
		key: "forecasting_max_group_variates",
		label: "Max Group Variates",
		description: "Maximum securities in one grouped multivariate request",
		type: "number",
		default: 32,
		min: 1,
		max: 256
	},
	{
		key: "forecasting_stale_after_days",
		label: "Stale Price Limit (days)",
		type: "number",
		default: 21,
		min: 1,
		max: 120
	},
	{
		key: "forecasting_max_missing_ratio",
		label: "Max Missing Input %",
		description: "Forecast run fails above this unusable-symbol ratio",
		type: "number",
		default: .25,
		min: 0,
		max: 100,
		step: .1,
		scale: 100
	},
	{
		key: "forecasting_score_max_age_days",
		label: "Score Freshness (days)",
		description: "Planner ignores forecast scores older than this",
		type: "number",
		default: 14,
		min: 1,
		max: 90
	},
	{
		key: "forecasting_timing_weight",
		label: "Timing Weight",
		description: "Maximum absolute opportunity-score adjustment",
		type: "number",
		default: .15,
		min: 0,
		max: .5,
		step: .001
	}
];
var researchGroups = [
	["Model and research tools", [
		{
			key: "ai_llm_base_url",
			label: "LLM URL",
			type: "text",
			default: ""
		},
		{
			key: "ai_llm_model",
			label: "Model",
			type: "model",
			default: ""
		},
		{
			key: "ai_llm_api_key",
			label: "LLM API key",
			type: "password",
			default: ""
		},
		{
			key: "ai_searxng_base_url",
			label: "Search URL",
			type: "text",
			default: ""
		},
		{
			key: "ai_browser_search_base_url",
			label: "Search fallback",
			type: "text",
			default: ""
		},
		{
			key: "ai_url_summarizer_base_url",
			label: "URL summarizer",
			type: "text",
			default: ""
		}
	]],
	["Research memory", [
		{
			key: "ai_pg_host",
			label: "PostgreSQL host",
			type: "text",
			default: ""
		},
		{
			key: "ai_pg_port",
			label: "PostgreSQL port",
			type: "number",
			default: 5432,
			min: 1,
			max: 65535
		},
		{
			key: "ai_pg_database",
			label: "Database",
			type: "text",
			default: ""
		},
		{
			key: "ai_pg_user",
			label: "Database user",
			type: "text",
			default: ""
		},
		{
			key: "ai_pg_password",
			label: "Database password",
			type: "password",
			default: ""
		},
		{
			key: "ai_embed_base_url",
			label: "Embedding URL",
			type: "text",
			default: ""
		},
		{
			key: "ai_embed_model",
			label: "Embedding model",
			type: "text",
			default: ""
		},
		{
			key: "ai_embed_dims",
			label: "Embedding dimensions",
			type: "number",
			default: 768,
			min: 1
		},
		{
			key: "ai_memory_user_id",
			label: "Memory user",
			type: "text",
			default: ""
		},
		{
			key: "ai_memory_collection",
			label: "Memory collection",
			type: "text",
			default: ""
		}
	]],
	["Cadence and limits", [
		{
			key: "ai_dedup_similarity_threshold",
			label: "Dedup similarity",
			type: "number",
			default: .96,
			min: 0,
			max: 1,
			step: .01
		},
		{
			key: "ai_llm_timeout_seconds",
			label: "LLM timeout (seconds)",
			type: "number",
			default: 3600,
			min: 1
		},
		{
			key: "ai_max_tool_calls",
			label: "Maximum tool calls",
			type: "number",
			default: 40,
			min: 1,
			max: 100
		},
		{
			key: "ai_max_tool_loop_iterations",
			label: "Maximum tool rounds",
			type: "number",
			default: 40,
			min: 1,
			max: 100
		}
	]]
];
var apiFields = [
	{
		key: "tradernet_api_key",
		label: "Tradernet API Key",
		description: "Your Tradernet public API key",
		type: "text",
		default: ""
	},
	{
		key: "tradernet_api_secret",
		label: "Tradernet API Secret",
		description: "Your Tradernet private API secret",
		type: "password",
		default: ""
	},
	{
		key: "freedom24_login",
		label: "Freedom24 Login",
		description: "Email used to sign in at freedom24.com",
		type: "text",
		default: ""
	},
	{
		key: "freedom24_password",
		label: "Freedom24 Password",
		description: "Web login password, not your API secret",
		type: "password",
		default: ""
	}
];
var backupFields = [
	{
		key: "r2_account_id",
		label: "R2 Account ID",
		description: "Your Cloudflare account ID",
		type: "text",
		default: ""
	},
	{
		key: "r2_access_key",
		label: "R2 Access Key",
		description: "R2 API token access key",
		type: "text",
		default: ""
	},
	{
		key: "r2_secret_key",
		label: "R2 Secret Key",
		description: "R2 API token secret key",
		type: "password",
		default: ""
	},
	{
		key: "r2_bucket_name",
		label: "R2 Bucket Name",
		description: "Name of the R2 bucket to store backups",
		type: "text",
		default: ""
	},
	{
		key: "r2_backup_retention_days",
		label: "Retention Days",
		description: "Automatically delete backups older than this",
		type: "number",
		default: 30,
		min: 1,
		max: 365
	}
];
var SentinelSettings = class extends i {
	static properties = {
		tab: { state: true },
		strategyDraft: { state: true },
		busyKey: { state: true },
		notice: { state: true },
		actionError: { state: true }
	};
	constructor() {
		super();
		this.tab = "trading";
		this.strategyDraft = void 0;
		this.busyKey = "";
		this.notice = "";
		this.actionError = "";
	}
	settings = new LiveResource(this, (signal) => getJson("/api/settings", { signal }), { interval: 0 });
	models = new LiveResource(this, (signal) => getJson("/api/ai/models", { signal }), { interval: 0 });
	createRenderRoot() {
		return this;
	}
	updated() {
		if (this.settings.value && !this.strategyDraft) this.strategyDraft = Object.fromEntries(strategyDraftFields.map((field) => [field.key, Number(this.settings.value[field.key] ?? field.default)]));
	}
	displayValue(field, source = this.settings.value) {
		const value = source?.[field.key] ?? field.default;
		return field.scale ? Number(value) * field.scale : value;
	}
	parseValue(field, value) {
		if (field.type !== "number") return value;
		const number = Number(value);
		return field.scale ? number / field.scale : number;
	}
	async updateSetting(field, value) {
		const parsed = this.parseValue(field, value);
		const previous = this.settings.value?.[field.key];
		this.busyKey = field.key;
		this.notice = "";
		this.actionError = "";
		this.settings.value = {
			...this.settings.value,
			[field.key]: parsed
		};
		this.requestUpdate();
		try {
			await putJson(`/api/settings/${encodeURIComponent(field.key)}`, { value: parsed });
			this.notice = `${field.label} saved`;
			window.dispatchEvent(new CustomEvent("sentinel-setting-changed", { detail: {
				key: field.key,
				value: parsed
			} }));
		} catch (error) {
			this.settings.value = {
				...this.settings.value,
				[field.key]: previous
			};
			this.actionError = error.message;
			this.requestUpdate();
		} finally {
			this.busyKey = "";
		}
	}
	changeStrategy(field, value) {
		this.strategyDraft = {
			...this.strategyDraft,
			[field.key]: Number(value)
		};
	}
	async applyStrategy() {
		this.busyKey = "strategy";
		this.notice = "";
		this.actionError = "";
		try {
			await putJson("/api/settings", { values: this.strategyDraft });
			this.settings.value = {
				...this.settings.value,
				...this.strategyDraft
			};
			this.notice = "Strategy tuning saved";
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.busyKey = "";
		}
	}
	renderField(field, source = this.settings.value, strategy = false) {
		const value = this.displayValue(field, source);
		const disabled = this.busyKey !== "";
		let control;
		if (field.type === "toggle") control = b`<tui-toggle
        ?checked=${Boolean(value)}
        ?disabled=${disabled}
        @change=${(event) => this.updateSetting(field, event.currentTarget.checked)}
        >${field.label}</tui-toggle
      >`;
		else if (field.type === "select") control = b`<label
        >${field.label}&nbsp;<tui-select
          value=${value}
          ?disabled=${disabled}
          @change=${(event) => this.updateSetting(field, event.currentTarget.value)}
        >
          ${field.options.map(([optionValue, label]) => b`
              <option value=${optionValue}>${label}</option>
            `)}
        </tui-select></label
      >`;
		else {
			const type = field.type === "password" ? "password" : field.type === "number" ? "number" : "text";
			control = b`<label
        ><span>${field.label}</span>
        <tui-input
          block
          type=${type}
          value=${value ?? ""}
          min=${field.min ?? ""}
          max=${field.max ?? ""}
          step=${field.step ?? (field.type === "number" ? 1 : "")}
          list=${field.type === "model" ? "sentinel-ai-models" : ""}
          ?disabled=${disabled}
          @change=${(event) => strategy ? this.changeStrategy(field, event.currentTarget.value) : this.updateSetting(field, event.currentTarget.value)}
        ></tui-input
      ></label>`;
		}
		return b`
      <div style="min-width: 0; overflow-wrap: anywhere">
        ${control}
        ${field.description ? b`<div>${field.description}</div>` : ""}
      </div>
    `;
	}
	renderFields(fields, source = this.settings.value, strategy = false) {
		return fields.map((field, index) => b`
        ${index > 0 ? b`<div aria-hidden="true">&nbsp;</div>` : ""}
        ${this.renderField(field, source, strategy)}
      `);
	}
	renderResearch() {
		return b`
      <datalist id="sentinel-ai-models">
        ${(this.models.value?.models ?? []).map((model) => b`<option value=${model}></option>`)}
      </datalist>
      ${researchGroups.map(([heading, fields], index) => b`
          ${index > 0 ? b`<div aria-hidden="true">&nbsp;</div>` : ""}
          <tui-box heading=${heading} border="single">
            <tui-flex align="start" wrap>
              ${fields.map((field) => b`
                  <div style="flex: 1 1 38ch; min-width: 0">
                    ${this.renderField(field)}
                  </div>
                `)}
            </tui-flex>
            ${heading === "Model and research tools" ? b`<div>
                    <tui-button @click=${() => this.models.refresh()}
                      >Refresh available models</tui-button
                    >
                    ${this.models.error ? b`<tui-text variant="error"
                            >${this.models.error.message}</tui-text
                          >` : ""}
                  </div>` : ""}
          </tui-box>
        `)}
    `;
	}
	renderPanel() {
		switch (this.tab) {
			case "fees": return this.renderFields(feeFields);
			case "strategy": return b`
          <tui-box heading="Strategy Tuning" border="single">
            ${this.renderFields(strategyDraftFields, this.strategyDraft, true)}
            <div aria-hidden="true">&nbsp;</div>
            <tui-button
              ?disabled=${this.busyKey !== ""}
              @click=${this.applyStrategy}
              >Apply Strategy Tuning</tui-button
            >
          </tui-box>
          <div aria-hidden="true">&nbsp;</div>
          ${this.renderFields(strategyFields)}
        `;
			case "forecasting": return this.renderFields(forecastFields);
			case "research": return this.renderResearch();
			case "api": return b`
          ${this.renderFields(apiFields.slice(0, 2))}
          <div aria-hidden="true">&nbsp;</div>
          <tui-box heading="Freedom24 web login" border="single">
            <div>
              Used only to fetch PRAAMS portfolio-structure data not exposed by
              the public API.
            </div>
            ${this.renderFields(apiFields.slice(2))}
          </tui-box>
        `;
			case "backup": return b`
          <div>
            Back up the database, runtime state, task definitions, and research
            artifacts to Cloudflare R2.
          </div>
          <div aria-hidden="true">&nbsp;</div>
          ${this.renderFields(backupFields)}
        `;
			default: return this.renderFields(tradingFields);
		}
	}
	render() {
		if (this.settings.loading && !this.settings.value) return b`<div>Loading settings…</div>`;
		if (this.settings.error) return b`<tui-text variant="error"
        >Error loading settings: ${this.settings.error.message}</tui-text
      >`;
		return b`
      <tui-radio-buttonset
        aria-label="Settings section"
        value=${this.tab}
        @change=${(event) => this.tab = event.currentTarget.value}
      >
        <tui-radio-button value="trading">Trading</tui-radio-button>
        <tui-radio-button value="fees">Fees</tui-radio-button>
        <tui-radio-button value="strategy">Strategy</tui-radio-button>
        <tui-radio-button value="forecasting">Forecasts</tui-radio-button>
        <tui-radio-button value="research">Research</tui-radio-button>
        <tui-radio-button value="api">API</tui-radio-button>
        <tui-radio-button value="backup">Backup</tui-radio-button>
      </tui-radio-buttonset>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderPanel()}
      ${this.busyKey ? b`<div aria-live="polite">Saving ${this.busyKey}…</div>` : ""}
      ${this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError ? b`<tui-text variant="error">${this.actionError}</tui-text>` : ""}
    `;
	}
};
customElements.define("sentinel-settings", SentinelSettings);
//#endregion
//#region src/sentinel-trades.js
var SentinelTrades = class extends i {
	static properties = {
		page: { state: true },
		symbol: { state: true },
		side: { state: true },
		startDate: { state: true },
		endDate: { state: true },
		syncing: { state: true },
		actionError: { state: true }
	};
	constructor() {
		super();
		this.page = 1;
		this.symbol = "";
		this.side = "";
		this.startDate = "";
		this.endDate = "";
		this.syncing = false;
		this.actionError = "";
	}
	pageSize = 20;
	securities = new LiveResource(this, (signal) => getJson("/api/securities", { signal }), { interval: 6e4 });
	trades = new LiveResource(this, (signal) => getJson(this.tradesPath, { signal }), { interval: 3e4 });
	createRenderRoot() {
		return this;
	}
	get tradesPath() {
		const parameters = new URLSearchParams({
			limit: String(this.pageSize),
			offset: String((this.page - 1) * this.pageSize)
		});
		if (this.symbol) parameters.set("symbol", this.symbol);
		if (this.side) parameters.set("side", this.side);
		if (this.startDate) parameters.set("start_date", this.startDate);
		if (this.endDate) parameters.set("end_date", this.endDate);
		return `/api/trades?${parameters}`;
	}
	changeFilter(name, value) {
		this[name] = value;
		this.page = 1;
		this.trades.refresh();
	}
	changePage(page) {
		this.page = page;
		this.trades.refresh();
	}
	async syncTrades() {
		this.syncing = true;
		this.actionError = "";
		try {
			await postJson("/api/trades/sync");
			await this.trades.refresh();
		} catch (error) {
			this.actionError = error.message;
		} finally {
			this.syncing = false;
		}
	}
	renderControls() {
		const symbols = (this.securities.value ?? []).map((security) => security.symbol).sort();
		return b`
      <tui-flex align="baseline" wrap>
        <label
          >Symbol&nbsp;<tui-select
            value=${this.symbol}
            @change=${(event) => this.changeFilter("symbol", event.currentTarget.value)}
          >
            <option value="">All symbols</option>
            ${symbols.map((symbol) => b`<option value=${symbol}>${symbol}</option>`)}
          </tui-select></label
        >
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <label
          >Side&nbsp;<tui-select
            value=${this.side}
            @change=${(event) => this.changeFilter("side", event.currentTarget.value)}
          >
            <option value="">All</option>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </tui-select></label
        >
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <label
          >From&nbsp;<tui-input
            type="date"
            value=${this.startDate}
            @change=${(event) => this.changeFilter("startDate", event.currentTarget.value)}
          ></tui-input
        ></label>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <label
          >To&nbsp;<tui-input
            type="date"
            value=${this.endDate}
            @change=${(event) => this.changeFilter("endDate", event.currentTarget.value)}
          ></tui-input
        ></label>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-button ?disabled=${this.syncing} @click=${this.syncTrades}
          >${this.syncing ? "Syncing…" : "Sync from Broker"}</tui-button
        >
      </tui-flex>
    `;
	}
	renderTable() {
		const trades = this.trades.value?.trades ?? [];
		if (trades.length === 0) return b`<div>No trades found</div>`;
		return b`
      <div style="overflow: auto; min-width: 0">
        <table style="border-collapse: collapse; width: 100%">
          <thead>
            <tr>
              <th style="text-align: left">Date</th>
              <th style="text-align: left">│ Symbol</th>
              <th style="text-align: left">│ Side</th>
              <th style="text-align: left">│ Qty</th>
              <th style="text-align: left">│ Price</th>
              <th style="text-align: left">│ Value</th>
              <th style="text-align: left">│ Commission</th>
              <th style="text-align: left">│ Currency</th>
            </tr>
          </thead>
          <tbody>
            ${trades.map((trade) => {
			const raw = trade.raw_data ?? {};
			const quantity = Number(raw.q ?? trade.quantity ?? 0);
			const price = Number(raw.p ?? trade.price ?? 0);
			const value = Number(raw.v ?? quantity * price);
			const commission = Number(raw.commiss_exchange ?? trade.commission ?? 0);
			const currency = raw.curr_c ?? trade.commission_currency ?? "-";
			return b`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${formatDateTime(trade.executed_at, { seconds: true })}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${trade.symbol}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │
                    <tui-text
                      variant=${trade.side === "BUY" ? "success" : "error"}
                      >${trade.side}</tui-text
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatNumber(quantity, 0)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatNumber(price, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatNumber(value, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${formatNumber(commission, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    │ ${currency}
                  </td>
                </tr>
              `;
		})}
          </tbody>
        </table>
      </div>
    `;
	}
	renderPagination() {
		const total = this.trades.value?.total ?? this.trades.value?.count ?? 0;
		const pages = Math.max(1, Math.ceil(total / this.pageSize));
		if (pages === 1) return "";
		return b`
      <div>
        <tui-button
          ?disabled=${this.page <= 1}
          @click=${() => this.changePage(this.page - 1)}
          >Previous</tui-button
        >
        Page ${this.page} / ${pages}
        <tui-button
          ?disabled=${this.page >= pages}
          @click=${() => this.changePage(this.page + 1)}
          >Next</tui-button
        >
      </div>
    `;
	}
	render() {
		if (this.securities.loading && !this.securities.value) return b`<div>Loading trade filters…</div>`;
		return b`
      ${this.renderControls()}
      <div aria-hidden="true">&nbsp;</div>
      ${this.trades.loading && !this.trades.value ? b`<div>Loading trades…</div>` : this.trades.error ? b`<tui-text variant="error"
                >Error loading trades: ${this.trades.error.message}</tui-text
              >` : this.renderTable()}
      ${this.renderPagination()}
      ${this.actionError ? b`<tui-text variant="error">${this.actionError}</tui-text>` : ""}
    `;
	}
};
customElements.define("sentinel-trades", SentinelTrades);
//#endregion
//#region src/sentinel-header.js
var actions = [
	{
		id: "backtest",
		label: "Backtest",
		heading: "Backtest",
		researchOnly: true
	},
	{
		id: "trades",
		label: "Trades",
		heading: "Trade History"
	},
	{
		id: "scheduler",
		label: "Scheduler",
		heading: "Scheduler"
	},
	{
		id: "research",
		label: "Research",
		heading: "Research Pipeline"
	},
	{
		id: "settings",
		label: "Settings",
		heading: "Settings"
	}
];
var SentinelHeader = class extends i {
	static properties = { activeModal: { state: true } };
	constructor() {
		super();
		this.activeModal = void 0;
	}
	health = new LiveResource(this, (signal) => getJson("/api/health", { signal }), { interval: 3e4 });
	refreshHealth = () => this.health.refresh();
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-setting-changed", this.refreshHealth);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-setting-changed", this.refreshHealth);
		super.disconnectedCallback();
	}
	createRenderRoot() {
		return this;
	}
	openModal(id) {
		this.activeModal = id;
	}
	closeModal(id) {
		if (this.activeModal === id) this.activeModal = void 0;
	}
	requestModalClose(event) {
		const contents = event.currentTarget.querySelectorAll("sentinel-backtest, sentinel-research, sentinel-scheduler, sentinel-settings, sentinel-tasks, sentinel-trades");
		for (const content of contents) if (content.confirmClose && !content.confirmClose()) {
			event.preventDefault();
			return;
		}
	}
	get visibleActions() {
		const live = this.health.value?.trading_mode === "live";
		return actions.filter((action) => !action.researchOnly || !live);
	}
	renderAction(action, index) {
		const modalId = `sentinel-${action.id}-modal`;
		return b`
      ${index > 0 ? b`<span aria-hidden="true">&nbsp;</span>` : ""}
      <tui-button
        aria-controls=${modalId}
        aria-expanded=${this.activeModal === action.id ? "true" : "false"}
        inverted
        @click=${() => this.openModal(action.id)}
        >${action.label}</tui-button
      >
    `;
	}
	renderModalContent(id) {
		switch (id) {
			case "backtest": return b`<sentinel-backtest></sentinel-backtest>`;
			case "trades": return b`<sentinel-trades></sentinel-trades>`;
			case "scheduler": return b`<sentinel-scheduler></sentinel-scheduler>`;
			case "research": return b`<sentinel-research></sentinel-research>`;
			case "settings": return b`<sentinel-settings></sentinel-settings>`;
			default: return "";
		}
	}
	renderModal() {
		const action = actions.find(({ id }) => id === this.activeModal);
		if (!action) return "";
		return b`
      <tui-modal
        id=${`sentinel-${action.id}-modal`}
        heading=${action.heading}
        open
        @cancel=${this.requestModalClose}
        @close=${() => this.closeModal(action.id)}
        >${this.renderModalContent(action.id)}</tui-modal
      >
    `;
	}
	render() {
		return b`
      <header>
        <tui-bar>
          <nav aria-label="Application">
            <tui-flex align="baseline" wrap>
              ${this.visibleActions.map((action, index) => this.renderAction(action, index))}
            </tui-flex>
          </nav>
        </tui-bar>
        ${this.renderModal()}
      </header>
    `;
	}
};
customElements.define("sentinel-header", SentinelHeader);
//#endregion
//#region src/sentinel-planner-status.js
var SentinelPlannerStatus = class extends i {
	planner = new LiveResource(this, (signal) => getJson("/api/planner/recommendations", { signal }), { interval: 6e4 });
	createRenderRoot() {
		return this;
	}
	renderRecommendation(recommendation, index) {
		const isSell = recommendation.action === "sell";
		const percentage = isSell && recommendation.current_value_eur > 0 ? ` ${Math.round(Math.abs(recommendation.value_delta_eur) / recommendation.current_value_eur * 100)}%` : "";
		return b`
      <tui-text variant=${isSell ? "error" : "success"} title=${recommendation.reason ?? ""}
        >${index > 0 ? b`<span aria-hidden="true">&nbsp;&nbsp;</span>` : ""}${recommendation.action.toUpperCase()}
        ${formatCurrency(Math.abs(recommendation.value_delta_eur))}${percentage}
        ${recommendation.symbol}</tui-text
      >
    `;
	}
	targetItems(plan) {
		if (!plan) return [];
		const cashTarget = {
			symbol: "CASH",
			target_value_eur: Number(plan.target_cash_value_eur ?? 0),
			gap_eur: Number(plan.cash_gap_eur ?? 0),
			isCash: true
		};
		const targets = [...plan.targets ?? []];
		if (cashTarget.target_value_eur > 0 || Number(plan.current_cash_eur ?? 0) > 0) targets.push(cashTarget);
		return targets.filter((target) => Math.abs(Number(target.gap_eur ?? 0)) > .005).sort((left, right) => Math.abs(Number(right.gap_eur)) - Math.abs(Number(left.gap_eur))).slice(0, 6);
	}
	renderTarget(target, index) {
		const gap = Number(target.gap_eur ?? 0);
		const quantityDelta = Number(target.quantity_delta ?? 0);
		const quantity = !target.isCash && Math.abs(quantityDelta) > 1e-4 ? b`&nbsp;·&nbsp;${quantityDelta > 0 ? "+" : "-"}${Math.abs(quantityDelta).toLocaleString()}
          sh` : "";
		return b`
      <span title=${target.isCash ? "Cash left after deploying all affordable whole-lot purchases" : `AI research ${Number(target.ai_research_multiplier ?? 0).toFixed(2)}, opportunity ${Number(target.opportunity_score ?? 0).toFixed(2)}`}
        >${index > 0 ? b`<span aria-hidden="true">&nbsp;&nbsp;</span>` : ""}${target.symbol}&nbsp;${formatCurrency(target.target_value_eur)}
        (${gap >= 0 ? "+" : "-"}${formatCurrency(Math.abs(gap))}${quantity})</span
      >
    `;
	}
	renderPlanner(planner) {
		const recommendations = planner.recommendations ?? [];
		const plan = planner.plan;
		const summary = planner.summary;
		const targets = this.targetItems(plan);
		const cycleLabel = summary?.valid_for_minutes ? `Next ${summary.valid_for_minutes} min:` : "Next cycle:";
		const gapLabel = `${plan?.horizon_months ?? 12} mo gaps:`;
		return b`
      <tui-flex wrap>
        <span>${cycleLabel}&nbsp;</span>
        ${recommendations.length > 0 ? recommendations.map((recommendation, index) => this.renderRecommendation(recommendation, index)) : b`<span>No pending actions</span>`}
      </tui-flex>
      <tui-flex wrap>
        <span>${gapLabel}&nbsp;</span>
        ${targets.length > 0 ? targets.map((target, index) => this.renderTarget(target, index)) : b`<span>Target unavailable</span>`}
      </tui-flex>
      ${plan ? b`
              <tui-flex wrap>
                <span
                  >${formatCurrency(plan.terminal_portfolio_value_eur)} by
                  ${plan.horizon_end_date}</span
                >
                <span aria-hidden="true">&nbsp;·&nbsp;</span>
                <span
                  >${formatCurrency(plan.avg_monthly_net_deposit_eur)}/mo</span
                >
                <span aria-hidden="true">&nbsp;·&nbsp;</span>
                <span>${(plan.targets ?? []).length} securities</span>
                ${summary ? b`
                        <span aria-hidden="true">&nbsp;·&nbsp;</span>
                        <span
                          >cash after today
                          ${formatCurrency(summary.cash_after_plan)}</span
                        >
                      ` : ""}
              </tui-flex>
            ` : ""}
    `;
	}
	render() {
		let content;
		if (this.planner.loading && !this.planner.value) content = b`<span>Loading plan…</span>`;
		else if (this.planner.error) content = b`<tui-text variant="error">Plan unavailable</tui-text>`;
		else content = this.renderPlanner(this.planner.value);
		return b`<tui-box heading="Plan" border="single">${content}</tui-box>`;
	}
};
customElements.define("sentinel-planner-status", SentinelPlannerStatus);
//#endregion
//#region src/sentinel-portfolio-pnl.js
var PERIODS = [
	"1D",
	"1W",
	"1M",
	"3M",
	"6M",
	"1Y",
	"YTD",
	"All"
];
function lastFinite(values) {
	return values.findLast(Number.isFinite);
}
function formatPnl(value) {
	if (value === null || value === void 0 || Number.isNaN(value)) return "-";
	const sign = value >= 0 ? "+" : "-";
	const absolute = Math.abs(value);
	if (absolute >= 1e6) return `${sign}€${(absolute / 1e6).toFixed(1)}M`;
	if (absolute >= 1e3) return `${sign}€${(absolute / 1e3).toFixed(1)}K`;
	return `${sign}€${absolute.toFixed(0)}`;
}
function valueVariant(value) {
	if (value > 0) return "success";
	if (value < 0) return "error";
}
var SentinelPortfolioPnl = class extends i {
	static properties = { pnlPeriod: { state: true } };
	constructor() {
		super();
		this.pnlPeriod = "1Y";
	}
	performance = new LiveResource(this, async (signal) => {
		const [periods, history] = await Promise.all([getJson("/api/portfolio/period-stats", { signal }), getJson(`/api/portfolio/pnl-history?period=${this.pnlPeriod}`, { signal })]);
		return {
			sinceInceptionMoneyWeightedReturn: periods.since_inception_money_weighted_return_pct,
			periodStats: periods.period_stats,
			snapshots: history.snapshots,
			summary: history.summary
		};
	}, { interval: 3e5 });
	createRenderRoot() {
		return this;
	}
	renderValue(value, formatted) {
		const variant = valueVariant(value);
		return variant ? b`<tui-text variant=${variant}>${formatted}</tui-text>` : b`<span>${formatted}</span>`;
	}
	renderSummary(summary, sinceInceptionMoneyWeightedReturn) {
		return b`
      <tui-flex align="baseline" justify="between" wrap>
        <span
          title="Annual investor-return target"
          style="white-space: nowrap"
          >Target p.a.&nbsp;${this.renderValue(summary.target_ann_return, formatPercent(summary.target_ann_return, 1))}</span
        >
        <tui-flex align="baseline" wrap>
          <span
            title="Money-weighted annual return using the date and amount of every deposit and withdrawal"
            style="white-space: nowrap"
            >Overall yearly return&nbsp;${this.renderValue(sinceInceptionMoneyWeightedReturn, formatPercent(sinceInceptionMoneyWeightedReturn, 1))}</span
          >
          <span
            title="Money-weighted annual return over the last 365 days, using the opening value and every deposit and withdrawal"
            style="white-space: nowrap"
            >&nbsp;│&nbsp;Last 365 days&nbsp;${this.renderValue(summary.trailing_365d_money_weighted_return_pct, formatPercent(summary.trailing_365d_money_weighted_return_pct, 1))}</span
          >
        </tui-flex>
      </tui-flex>
    `;
	}
	renderTable(periodStats) {
		return b`
      <table
        aria-label="Portfolio performance by period"
        style="border-spacing: 0"
      >
        <thead>
          <tr>
            <th scope="col" style="text-align: left">Period&nbsp;&nbsp;</th>
            <th scope="col" style="text-align: right">P/L&nbsp;&nbsp;</th>
            <th scope="col" style="text-align: right">Return</th>
          </tr>
        </thead>
        <tbody>
          ${PERIODS.map((period) => {
			const row = periodStats[period] ?? {};
			return b`
              <tr>
                <th scope="row" style="font: inherit; text-align: left">
                  ${period}&nbsp;&nbsp;
                </th>
                <td style="text-align: right">
                  ${this.renderValue(row.portfolio_eur, formatPnl(row.portfolio_eur))}&nbsp;&nbsp;
                </td>
                <td style="text-align: right">
                  ${this.renderValue(row.portfolio_pct, formatPercent(row.portfolio_pct, 1))}
                </td>
              </tr>
            `;
		})}
        </tbody>
      </table>
    `;
	}
	changePeriod(event) {
		this.pnlPeriod = event.currentTarget.value;
		this.performance.refresh();
	}
	renderControls() {
		return b`
      <tui-flex align="baseline" wrap>
        <span>Range&nbsp;</span>
        <tui-radio-buttonset
          aria-label="P/L chart period"
          value=${this.pnlPeriod}
          @change=${this.changePeriod}
        >
          <tui-radio-button value="3M">3M</tui-radio-button>
          <tui-radio-button value="6M">6M</tui-radio-button>
          <tui-radio-button value="1Y">1Y</tui-radio-button>
          <tui-radio-button value="ALL">ALL</tui-radio-button>
        </tui-radio-buttonset>
      </tui-flex>
    `;
	}
	renderChartRow(label, values, latest, minimum, maximum, threshold) {
		const comparison = Number.isFinite(latest) && Number.isFinite(threshold) ? latest - threshold : void 0;
		return b`
      <tui-flex align="start">
        <span
          data-chart-space
          style="display: block; flex: 1 1 0; min-width: 0; white-space: nowrap"
          >${b`<tui-chart
      aria-label="${label} annualized return trend"
      height="4"
      min=${minimum}
      max=${maximum}
      threshold=${threshold ?? ""}
      above-variant="success"
      below-variant="error"
      .values=${values}
    ></tui-chart>`}</span
        >
        <span style="white-space: nowrap"
          >&nbsp;${Number.isFinite(comparison) ? this.renderValue(comparison, formatPercent(latest, 1)) : formatPercent(latest, 1)}</span
        >
      </tui-flex>
    `;
	}
	renderChart(snapshots, summary) {
		if (!snapshots || snapshots.length < 2) return b`<span>Not enough data yet</span>`;
		const actual = snapshots.map((snapshot) => snapshot.rolling_365d_money_weighted_return_pct === null ? void 0 : Number(snapshot.rolling_365d_money_weighted_return_pct));
		const target = Number(summary.target_ann_return);
		const scaleValues = actual.filter(Number.isFinite);
		const dataMinimum = Math.min(...scaleValues, target);
		const dataMaximum = Math.max(...scaleValues, target);
		const extent = Math.max(1, target - dataMinimum, dataMaximum - target) * 1.2;
		const minimum = target - extent;
		const maximum = target + extent;
		const actualLatest = lastFinite(actual);
		return this.renderChartRow("365d MWR", actual, actualLatest, minimum, maximum, target);
	}
	render() {
		let content;
		if (this.performance.loading && !this.performance.value) content = b`<span>Loading performance…</span>`;
		else if (this.performance.error) content = b`<tui-text variant="error"
        >Portfolio P&amp;L unavailable</tui-text
      >`;
		else if (!this.performance.value?.periodStats || !this.performance.value?.summary) content = b`<span>Not enough data yet</span>`;
		else content = b`
        ${this.renderSummary(this.performance.value.summary, this.performance.value.sinceInceptionMoneyWeightedReturn)}
        ${this.renderControls()}
        ${this.renderChart(this.performance.value.snapshots, this.performance.value.summary)}
        ${this.renderTable(this.performance.value.periodStats)}
      `;
		return b`<tui-box heading="Portfolio P&amp;L" border="single"
      >${content}</tui-box
    >`;
	}
};
customElements.define("sentinel-portfolio-pnl", SentinelPortfolioPnl);
//#endregion
//#region src/sentinel-portfolio-status.js
var SentinelPortfolioStatus = class extends i {
	portfolio = new LiveResource(this, (signal) => getJson("/api/portfolio", { signal }), { interval: 6e4 });
	cashFlows = new LiveResource(this, (signal) => getJson("/api/cashflows", { signal }), { interval: 3e5 });
	createRenderRoot() {
		return this;
	}
	renderCashBreakdown(cash) {
		const balances = Object.entries(cash ?? {}).filter(([, amount]) => amount !== 0);
		if (balances.length === 0) return "";
		return b`&nbsp;(${balances.map(([currency, amount], index) => b`${index > 0 ? ", " : ""}${currency}&nbsp;${formatCurrency(amount, currency)}`)})`;
	}
	renderPortfolio() {
		const portfolio = this.portfolio.value;
		return b`
      <tui-flex wrap>
        <span
          >Value&nbsp;<strong
            >${formatCurrency(portfolio.total_value_eur)}</strong
          ></span
        >
        <span aria-hidden="true">&nbsp;&nbsp;│&nbsp;&nbsp;</span>
        <span
          >Cash&nbsp;<strong>${formatCurrency(portfolio.total_cash_eur)}</strong>${this.renderCashBreakdown(portfolio.cash)}</span
        >
      </tui-flex>
    `;
	}
	renderCashFlows() {
		const cashFlows = this.cashFlows.value;
		if (!cashFlows) return "";
		const totalFees = cashFlows.fees + cashFlows.taxes;
		const profitVariant = cashFlows.total_profit >= 0 ? "success" : "error";
		return b`
      <tui-flex wrap>
        <span
          >Deposits&nbsp;<tui-text variant="success"
            >${formatCurrency(cashFlows.deposits)}</tui-text
          ></span
        >
        <span aria-hidden="true">&nbsp;&nbsp;│&nbsp;&nbsp;</span>
        <span
          >Withdrawals&nbsp;<tui-text variant="error"
            >${formatCurrency(cashFlows.withdrawals)}</tui-text
          ></span
        >
        <span aria-hidden="true">&nbsp;&nbsp;│&nbsp;&nbsp;</span>
        <span
          >Dividends&nbsp;<tui-text variant="success"
            >${formatCurrency(cashFlows.dividends)}</tui-text
          ></span
        >
        <span aria-hidden="true">&nbsp;&nbsp;│&nbsp;&nbsp;</span>
        <span
          >Fees&nbsp;<tui-text variant="error"
            >${formatCurrency(totalFees)}</tui-text
          ></span
        >
        <span aria-hidden="true">&nbsp;&nbsp;—&nbsp;&nbsp;</span>
        <span
          >Total Profit&nbsp;<tui-text variant=${profitVariant}
            >${formatCurrency(cashFlows.total_profit)}</tui-text
          ></span
        >
      </tui-flex>
    `;
	}
	render() {
		let content;
		if (this.portfolio.loading && !this.portfolio.value) content = b`<span>Loading portfolio…</span>`;
		else if (this.portfolio.error) content = b`<tui-text variant="error"
        >Portfolio unavailable</tui-text
      >`;
		else content = this.renderPortfolio();
		return b`<section aria-label="Portfolio status">
      ${content}${this.renderCashFlows()}
    </section>`;
	}
};
customElements.define("sentinel-portfolio-status", SentinelPortfolioStatus);
//#endregion
//#region src/sentinel-portfolio-value.js
var CHECKPOINT_COUNT = 5;
var CHECKPOINT_INTERVAL = 5;
function formatSignedCurrency(value, currency = "EUR", fractionDigits = 0) {
	if (value === null || value === void 0) return "-";
	return `${value > 0 ? "+" : ""}${formatCurrency(value, currency, fractionDigits)}`;
}
function checkpointDates(currentDate) {
	const current = /* @__PURE__ */ new Date(`${currentDate}T00:00:00Z`);
	if (Number.isNaN(current.getTime())) return [];
	const firstYear = Math.floor(current.getUTCFullYear() / CHECKPOINT_INTERVAL) * CHECKPOINT_INTERVAL + 5;
	const month = current.getUTCMonth();
	const day = current.getUTCDate();
	return Array.from({ length: CHECKPOINT_COUNT }, (_, index) => {
		const year = firstYear + index * CHECKPOINT_INTERVAL;
		const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
		return new Date(Date.UTC(year, month, Math.min(day, lastDay)));
	});
}
function closestProjection(projection, target) {
	let closest;
	let closestDistance = Number.POSITIVE_INFINITY;
	for (const point of projection) {
		const date = Date.parse(`${point.date}T00:00:00Z`);
		const distance = Math.abs(date - target.getTime());
		if (Number.isFinite(date) && distance < closestDistance) {
			closest = point;
			closestDistance = distance;
		}
	}
	return closest;
}
var SentinelPortfolioValue = class extends i {
	projection = new LiveResource(this, (signal) => getJson("/api/portfolio/value-projection?years=25", { signal }), { interval: 3e5 });
	createRenderRoot() {
		return this;
	}
	projectionRows(data) {
		return checkpointDates(data.summary.current_date).map((date) => {
			const point = closestProjection(data.projection, date);
			if (!point) return;
			return {
				date,
				point,
				projectedNetDeposits: data.summary.current_net_deposits_eur + data.summary.avg_monthly_net_deposit_eur * point.months_ahead
			};
		}).filter(Boolean);
	}
	renderMetrics(summary, startYear, endYear) {
		const pnlVariant = summary.total_pnl_pct >= 0 ? "success" : "error";
		const runRateVariant = Number.isFinite(summary.annualized_total_pnl_pct) ? summary.annualized_total_pnl_pct >= 0 ? "success" : "error" : void 0;
		return b`
      <tui-flex wrap>
        <span style="white-space: nowrap">${startYear} to ${endYear}</span>
        <span
          title="Cumulative profit: current portfolio value minus net funding; the percentage is relative to deposits minus withdrawals"
          style="white-space: nowrap"
          >&nbsp;&nbsp;Total P/L&nbsp;<tui-text variant=${pnlVariant}
            >${formatSignedCurrency(summary.total_pnl_eur)}
            (${formatPercent(summary.total_pnl_pct, 1)} of net funding)</tui-text
          ></span
        >
        <span style="white-space: nowrap"
          >&nbsp;&nbsp;${summary.deposit_window_months}M
          net/mo&nbsp;${formatCurrency(summary.avg_monthly_net_deposit_eur, "EUR", 0)}</span
        >
        <span
          title="Since-inception money-weighted annual return used as the projection growth assumption"
          style="white-space: nowrap"
          >&nbsp;&nbsp;Historical MWR p.a.&nbsp;<tui-text variant=${runRateVariant}
            >${formatPercent(summary.annualized_total_pnl_pct, 1)}</tui-text
          ></span
        >
      </tui-flex>
    `;
	}
	renderTable(checkpoints) {
		if (checkpoints.length === 0) return b`<span>Not enough data yet</span>`;
		return b`
      <table aria-label="Portfolio value projections" style="border-spacing: 0">
        <thead>
          <tr>
            <th scope="col" style="text-align: left">Year&nbsp;&nbsp;</th>
            <th scope="col" style="text-align: right">Value&nbsp;&nbsp;</th>
            <th
              scope="col"
              aria-label="Projected net deposits"
              style="text-align: right"
            >
              Net deposits
            </th>
          </tr>
        </thead>
        <tbody>
          ${checkpoints.map(({ date, point, projectedNetDeposits }) => b`
              <tr>
                <th scope="row" style="font: inherit; text-align: left">
                  ${date.getUTCFullYear()}&nbsp;&nbsp;
                </th>
                <td style="text-align: right">
                  ${formatCurrency(point.projected_value_eur, "EUR", 0)}&nbsp;&nbsp;
                </td>
                <td style="text-align: right">
                  ${formatCurrency(projectedNetDeposits, "EUR", 0)}
                </td>
              </tr>
            `)}
        </tbody>
      </table>
    `;
	}
	renderProjection(data) {
		const checkpoints = this.projectionRows(data);
		if (checkpoints.length === 0) return b`<span>Not enough data yet</span>`;
		const startYear = String(data.summary.start_date).slice(0, 4);
		const endYear = checkpoints.at(-1).date.getUTCFullYear();
		return b`${this.renderMetrics(data.summary, startYear, endYear)}
    ${this.renderTable(checkpoints)}`;
	}
	render() {
		let content;
		if (this.projection.loading && !this.projection.value) content = b`<span>Loading projection…</span>`;
		else if (this.projection.error) content = b`<tui-text variant="error"
        >Projection unavailable</tui-text
      >`;
		else if (!this.projection.value?.summary || !this.projection.value?.projection?.length) content = b`<span>Not enough data yet</span>`;
		else content = this.renderProjection(this.projection.value);
		return b`<tui-box heading="Portfolio value" border="single"
      >${content}</tui-box
    >`;
	}
};
customElements.define("sentinel-portfolio-value", SentinelPortfolioValue);
//#endregion
//#region src/sentinel-securities.js
var COLUMN_SETTING_KEY = "ui_securities_table_columns";
var DEFAULT_COLUMNS = [
	"price",
	"security",
	"value",
	"pnl",
	"ideal",
	"plan",
	"trade"
];
function plainPercent(value, fractionDigits = 1) {
	const number = Number(value);
	return Number.isFinite(number) ? `${number.toFixed(fractionDigits)}%` : "-";
}
function scorePercent(value, fractionDigits = 0) {
	const number = Number(value);
	return Number.isFinite(number) ? `${(number * 100).toFixed(fractionDigits)}%` : "-";
}
function variantFor(value) {
	const number = Number(value);
	if (number > 0) return "success";
	if (number < 0) return "error";
}
function recommendationValue(security) {
	const recommendation = security.recommendation;
	if (!recommendation) return 0;
	return (recommendation.action === "buy" ? 1 : -1) * Math.abs(Number(recommendation.value_delta_eur) || 0);
}
function safeId(symbol) {
	return String(symbol).replaceAll(/[^a-zA-Z0-9_-]/g, "-");
}
var SentinelSecurities = class extends i {
	static properties = {
		period: { state: true },
		search: { state: true },
		expandedSymbols: { state: true },
		sortColumn: { state: true },
		sortReversed: { state: true },
		busyAction: { state: true },
		message: { state: true },
		errorMessage: { state: true },
		addError: { state: true },
		deleteCandidate: { state: true },
		visibleColumns: { state: true },
		columnsBusy: { state: true },
		activeRowSymbol: { state: true },
		inactiveOnly: {
			type: Boolean,
			attribute: "inactive-only"
		},
		bare: { type: Boolean }
	};
	constructor() {
		super();
		this.period = "1Y";
		this.search = "";
		this.expandedSymbols = /* @__PURE__ */ new Set();
		this.sortColumn = "ideal";
		this.sortReversed = true;
		this.busyAction = "";
		this.message = "";
		this.errorMessage = "";
		this.addError = "";
		this.deleteCandidate = void 0;
		this.visibleColumns = void 0;
		this.columnsBusy = false;
		this.activeRowSymbol = void 0;
		this.inactiveOnly = false;
		this.bare = false;
		this.securityListChanged = (event) => {
			if (event.target !== this) this.securities.refresh();
		};
	}
	securities = new LiveResource(this, (signal) => getJson(`/api/unified?period=${this.period}${this.inactiveOnly ? "&inactive_only=true" : ""}`, { signal }), { interval: 6e4 });
	columnSettings = new LiveResource(this, (signal) => getJson("/api/settings", { signal }), { interval: 0 });
	createRenderRoot() {
		return this;
	}
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-security-list-change", this.securityListChanged);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-security-list-change", this.securityListChanged);
		super.disconnectedCallback();
	}
	get allSecurities() {
		return this.securities.value ?? [];
	}
	get visibleSecurities() {
		const term = this.search.trim().toLowerCase();
		return this.allSecurities.filter((security) => {
			if (!term) return true;
			return [
				security.symbol,
				security.name,
				security.geography,
				security.industry
			].filter(Boolean).some((value) => String(value).toLowerCase().includes(term));
		}).sort((left, right) => {
			let result;
			switch (this.sortColumn) {
				case "symbol":
					result = String(left.symbol).localeCompare(String(right.symbol));
					break;
				case "value":
					result = Number(left.value_eur || 0) - Number(right.value_eur || 0);
					break;
				case "pnl":
					result = Number(left.profit_pct || 0) - Number(right.profit_pct || 0);
					break;
				case "ideal":
					result = Number(left.ideal_allocation || 0) - Number(right.ideal_allocation || 0);
					break;
				case "recommendation":
					result = recommendationValue(left) - recommendationValue(right);
					break;
				default: result = (left.recommendation?.execution_rank ?? Number.POSITIVE_INFINITY) - (right.recommendation?.execution_rank ?? Number.POSITIVE_INFINITY) || String(left.symbol).localeCompare(String(right.symbol));
			}
			return this.sortReversed ? -result : result;
		});
	}
	get selectedColumns() {
		const configured = this.visibleColumns ?? this.columnSettings.value?.[COLUMN_SETTING_KEY];
		const valid = Array.isArray(configured) ? configured.filter((column) => DEFAULT_COLUMNS.includes(column)) : [];
		const selected = new Set(valid.length > 0 ? valid : DEFAULT_COLUMNS);
		selected.add("security");
		return selected;
	}
	columnVisible(column) {
		return this.selectedColumns.has(column);
	}
	activateRow(symbol) {
		this.activeRowSymbol = symbol;
	}
	deactivateRow(symbol) {
		if (this.activeRowSymbol === symbol) this.activeRowSymbol = void 0;
	}
	rowFocusOut(event, symbol) {
		if (!event.currentTarget.contains(event.relatedTarget)) this.deactivateRow(symbol);
	}
	headingRowStyle(symbol) {
		if (this.activeRowSymbol !== symbol && !this.expandedSymbols.has(symbol)) return "";
		return [
			"background:light-dark(black,white)",
			"color:light-dark(white,black)",
			"--tui-color:light-dark(white,black)",
			"--tui-background:light-dark(black,white)",
			"--tui-success-color:light-dark(white,black)",
			"--tui-warning-color:light-dark(white,black)",
			"--tui-error-color:light-dark(white,black)"
		].join(";");
	}
	get stats() {
		return {
			total: this.allSecurities.length,
			positions: this.allSecurities.filter((security) => security.has_position).length,
			buys: this.allSecurities.filter((security) => security.recommendation?.action === "buy").length,
			sells: this.allSecurities.filter((security) => security.recommendation?.action === "sell").length
		};
	}
	renderColored(value, formatted) {
		const variant = variantFor(value);
		return variant ? b`<tui-text variant=${variant}>${formatted}</tui-text>` : formatted;
	}
	changePeriod(event) {
		this.period = event.currentTarget.value;
		this.securities.refresh();
		this.dispatchEvent(new CustomEvent("sentinel-security-period-change", {
			bubbles: true,
			composed: true,
			detail: { period: this.period }
		}));
	}
	changeSearch(event) {
		this.search = event.currentTarget.value;
	}
	changeSort(column) {
		if (this.sortColumn === column) {
			this.sortReversed = !this.sortReversed;
			return;
		}
		this.sortColumn = column;
		this.sortReversed = false;
	}
	sortMarker(column) {
		if (this.sortColumn !== column) return "↕";
		return this.sortReversed ? "↓" : "↑";
	}
	toggleExpanded(symbol) {
		const expanded = new Set(this.expandedSymbols);
		if (expanded.has(symbol)) expanded.delete(symbol);
		else expanded.add(symbol);
		this.expandedSymbols = expanded;
	}
	toggleAll() {
		const symbols = this.visibleSecurities.map((security) => security.symbol);
		const allExpanded = symbols.length > 0 && symbols.every((symbol) => this.expandedSymbols.has(symbol));
		this.expandedSymbols = allExpanded ? /* @__PURE__ */ new Set() : new Set(symbols);
	}
	updateLocalSecurity(symbol, updates) {
		this.securities.value = this.allSecurities.map((security) => security.symbol === symbol ? {
			...security,
			...updates
		} : security);
		this.requestUpdate();
	}
	async updatePermission(event, security, field) {
		const value = event.currentTarget.checked ? 1 : 0;
		const previous = security[field];
		this.errorMessage = "";
		this.message = "";
		this.updateLocalSecurity(security.symbol, { [field]: value });
		try {
			await putJson(`/api/securities/${encodeURIComponent(security.symbol)}`, { [field]: value });
			this.message = `${security.symbol} ${field === "allow_buy" ? "buy" : "sell"} permission updated`;
		} catch (error) {
			this.updateLocalSecurity(security.symbol, { [field]: previous });
			this.errorMessage = error.message;
		}
	}
	async saveAliases(security) {
		const input = this.querySelector(`#aliases-${safeId(security.symbol)}`);
		if (!input) return;
		this.busyAction = `aliases:${security.symbol}`;
		this.errorMessage = "";
		this.message = "";
		try {
			await putJson(`/api/securities/${encodeURIComponent(security.symbol)}`, { aliases: input.value });
			this.updateLocalSecurity(security.symbol, { aliases: input.value });
			this.message = `${security.symbol} aliases updated`;
		} catch (error) {
			this.errorMessage = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	openAddDialog() {
		this.addError = "";
		this.querySelector("#add-security-dialog")?.showModal();
	}
	openColumnsDialog() {
		this.errorMessage = "";
		this.querySelector("#columns-dialog")?.showModal();
	}
	closeColumnsDialog() {
		this.querySelector("#columns-dialog")?.close();
	}
	async toggleColumn(event, column) {
		const previous = this.selectedColumns;
		const next = new Set(previous);
		if (event.currentTarget.checked) next.add(column);
		else next.delete(column);
		if (next.size === 0) {
			event.currentTarget.setAttribute("checked", "");
			this.errorMessage = "At least one table column must remain visible";
			return;
		}
		const ordered = DEFAULT_COLUMNS.filter((candidate) => next.has(candidate));
		this.visibleColumns = ordered;
		this.columnsBusy = true;
		this.errorMessage = "";
		try {
			await putJson(`/api/settings/${COLUMN_SETTING_KEY}`, { value: ordered });
			this.columnSettings.value = {
				...this.columnSettings.value,
				[COLUMN_SETTING_KEY]: ordered
			};
		} catch (error) {
			this.visibleColumns = [...previous];
			this.errorMessage = error.message;
		} finally {
			this.columnsBusy = false;
		}
	}
	closeAddDialog() {
		this.querySelector("#add-security-dialog")?.close();
	}
	async addSecurity(event) {
		event.preventDefault();
		const input = this.querySelector("#add-security-symbol");
		const symbol = input?.value.trim().toUpperCase();
		if (!symbol) {
			this.addError = "Symbol is required";
			return;
		}
		this.busyAction = "add";
		this.addError = "";
		try {
			await postJson("/api/securities", { symbol });
			this.closeAddDialog();
			input.value = "";
			this.message = `${symbol} added`;
			await this.securities.refresh();
		} catch (error) {
			this.addError = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async openDeleteDialog(security) {
		this.deleteCandidate = security;
		this.errorMessage = "";
		await this.updateComplete;
		this.querySelector("#delete-security-dialog")?.showModal();
	}
	closeDeleteDialog() {
		this.querySelector("#delete-security-dialog")?.close();
	}
	async deleteSecurity() {
		const security = this.deleteCandidate;
		if (!security) return;
		this.busyAction = `delete:${security.symbol}`;
		this.errorMessage = "";
		try {
			await deleteJson(`/api/securities/${encodeURIComponent(security.symbol)}?sell_position=false`);
			this.closeDeleteDialog();
			this.expandedSymbols = new Set([...this.expandedSymbols].filter((symbol) => symbol !== security.symbol));
			this.message = this.inactiveOnly ? `${security.symbol} permanently deleted` : `${security.symbol} removed`;
			this.deleteCandidate = void 0;
			await this.securities.refresh();
			this.dispatchEvent(new CustomEvent("sentinel-security-list-change", {
				bubbles: true,
				composed: true
			}));
		} catch (error) {
			this.errorMessage = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	async activateSecurity(security) {
		this.busyAction = `activate:${security.symbol}`;
		this.errorMessage = "";
		this.message = "";
		try {
			await postJson("/api/securities", { symbol: security.symbol });
			this.expandedSymbols = new Set([...this.expandedSymbols].filter((symbol) => symbol !== security.symbol));
			this.message = `${security.symbol} activated`;
			await this.securities.refresh();
			this.dispatchEvent(new CustomEvent("sentinel-security-list-change", {
				bubbles: true,
				composed: true
			}));
		} catch (error) {
			this.errorMessage = error.message;
		} finally {
			this.busyAction = "";
		}
	}
	renderControls() {
		if (this.inactiveOnly) return "";
		return b`
      <tui-flex align="baseline" wrap>
        <span>Period&nbsp;</span>
        <tui-radio-buttonset
          aria-label="Security price period"
          value=${this.period}
          @change=${this.changePeriod}
        >
          <tui-radio-button value="1M">1M</tui-radio-button>
          <tui-radio-button value="1Y">1Y</tui-radio-button>
          <tui-radio-button value="5Y">5Y</tui-radio-button>
          <tui-radio-button value="10Y">10Y</tui-radio-button>
        </tui-radio-buttonset>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <label>
          Search&nbsp;<tui-input
            type="search"
            aria-label="Search securities"
            placeholder="symbol or name"
            size="14"
            @input=${this.changeSearch}
          ></tui-input>
        </label>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-button @click=${this.openColumnsDialog}>Columns</tui-button>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-button @click=${this.openAddDialog}>Add Security</tui-button>
      </tui-flex>
    `;
	}
	renderStats() {
		if (this.inactiveOnly) return "";
		const stats = this.stats;
		return b`
      <div>
        ${stats.total} securities&nbsp;│&nbsp;${stats.positions}
        positions&nbsp;│&nbsp;
        <tui-text variant="success">${stats.buys} buy signals</tui-text
        >&nbsp;│&nbsp;
        <tui-text variant="error">${stats.sells} sell signals</tui-text
        >&nbsp;│&nbsp; ${this.visibleSecurities.length} shown
      </div>
    `;
	}
	renderSortableHeader(label, column) {
		return b`
      <th
        scope="col"
        aria-sort=${this.sortColumn === column ? this.sortReversed ? "descending" : "ascending" : "none"}
        style="text-align: left; vertical-align: top"
      >
        <span aria-hidden="true">│&nbsp;</span
        ><tui-button @click=${() => this.changeSort(column)}
          >${label}</tui-button
        ><span aria-hidden="true">${this.sortMarker(column)}</span>
      </th>
    `;
	}
	renderRecommendation(security) {
		const recommendation = security.recommendation;
		if (!recommendation) return b`<span>-</span>`;
		return b`<tui-text variant=${recommendation.action === "buy" ? "success" : "error"}
      >${recommendation.action.toUpperCase()}
      ${formatCurrency(Math.abs(recommendation.value_delta_eur), "EUR")}</tui-text
    >`;
	}
	renderPriceSparkline(security) {
		const values = (security.prices ?? []).map((price) => Number(price.close)).filter(Number.isFinite);
		if (values.length < 2) return "-";
		const averageCost = Number(security.avg_cost);
		const hasAverageCost = Boolean(security.has_position) && averageCost > 0;
		const scaleValues = hasAverageCost ? [...values, averageCost] : values;
		const minimum = Math.min(...scaleValues);
		const maximum = Math.max(...scaleValues);
		return b`<tui-sparkline
      aria-label=${hasAverageCost ? `${security.symbol} price history; green above and red below average purchase price` : `${security.symbol} price history; no position`}
      columns="8"
      min=${minimum}
      max=${maximum}
      threshold=${hasAverageCost ? averageCost : ""}
      above-variant=${hasAverageCost ? "success" : ""}
      below-variant=${hasAverageCost ? "error" : ""}
      .values=${values}
    ></tui-sparkline>`;
	}
	renderSecurityRow(security) {
		const expanded = this.expandedSymbols.has(security.symbol);
		const detailsId = `security-${safeId(security.symbol)}-details`;
		const allocationChange = Math.abs(security.post_plan_allocation - security.current_allocation) > .5;
		const idealDifference = security.ideal_allocation - security.current_allocation;
		return b`
      <tr
        style=${this.headingRowStyle(security.symbol)}
        @mouseenter=${() => this.activateRow(security.symbol)}
        @mouseleave=${() => this.deactivateRow(security.symbol)}
        @focusin=${() => this.activateRow(security.symbol)}
        @focusout=${(event) => this.rowFocusOut(event, security.symbol)}
      >
        <td style="vertical-align: top">
          ${expanded ? b`<tui-button
                  aria-label="Collapse ${security.symbol}"
                  aria-expanded="true"
                  aria-controls=${detailsId}
                  @click=${() => this.toggleExpanded(security.symbol)}
                  >−</tui-button
                >` : b`<tui-button
                  aria-label="Expand ${security.symbol}"
                  aria-expanded="false"
                  aria-controls=${detailsId}
                  @click=${() => this.toggleExpanded(security.symbol)}
                  >+</tui-button
                >`}
        </td>
        ${this.columnVisible("price") ? b`<td style="vertical-align: top; white-space: nowrap">
                <span aria-hidden="true">│&nbsp;</span>
                ${this.renderPriceSparkline(security)}
              </td>` : ""}
        <th
          scope="row"
          style="font: inherit; text-align: left; vertical-align: top; overflow-wrap: anywhere"
        >
          <span aria-hidden="true">│&nbsp;</span>
          ${security.price_warning ? b`<tui-text variant="warning">!&nbsp;</tui-text>` : ""}<span
            style="white-space: nowrap"
            >${security.symbol}</span
          >
        </th>
        ${this.columnVisible("value") ? b`<td
                style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${security.has_position ? formatCurrency(security.value_eur, "EUR", 0) : "-"}
              </td>` : ""}
        ${this.columnVisible("pnl") ? b`<td
                style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${security.has_position ? b`${this.renderColored(security.profit_pct, formatPercent(security.profit_pct, 1))}&nbsp;${this.renderColored(security.profit_value_eur, formatCurrency(security.profit_value_eur, "EUR", 0))}` : "-"}
              </td>` : ""}
        ${this.columnVisible("ideal") ? b`<td style="text-align: left; vertical-align: top">
                <span aria-hidden="true">│&nbsp;</span>
                ${this.renderColored(idealDifference, plainPercent(security.ideal_allocation))}
              </td>` : ""}
        ${this.columnVisible("plan") ? b`<td
                style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${plainPercent(security.current_allocation)}
                ${allocationChange ? b`&nbsp;→&nbsp;${this.renderColored(security.post_plan_allocation - security.current_allocation, plainPercent(security.post_plan_allocation))}` : ""}
                <div>${this.renderRecommendation(security)}</div>
              </td>` : ""}
        ${this.columnVisible("trade") ? b`<td
                style="text-align: left; vertical-align: top; white-space: nowrap"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${this.inactiveOnly ? "Inactive" : b`<tui-toggle
                          aria-label="Allow buying ${security.symbol}"
                          ?checked=${security.allow_buy === 1}
                          @change=${(event) => this.updatePermission(event, security, "allow_buy")}
                          >B</tui-toggle
                        >&nbsp;<tui-toggle
                          aria-label="Allow selling ${security.symbol}"
                          ?checked=${security.allow_sell === 1}
                          @change=${(event) => this.updatePermission(event, security, "allow_sell")}
                          >S</tui-toggle
                        >`}
              </td>` : ""}
      </tr>
      ${expanded ? this.renderExpandedRow(security, detailsId) : ""}
    `;
	}
	renderDetailRow(label, value) {
		return b`
      <tr>
        <th
          scope="row"
          style="font: inherit; text-align: left; vertical-align: top; white-space: nowrap; padding-right: 1ch"
        >
          ${label}
        </th>
        <td
          style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
        >
          <span aria-hidden="true">│&nbsp;</span>${value}
        </td>
      </tr>
    `;
	}
	renderPriceChart(security) {
		const values = (security.prices ?? []).map((price) => Number(price.close)).filter(Number.isFinite);
		if (values.length < 2) return b`<div>No price data</div>`;
		const averageCost = Number(security.avg_cost);
		const hasAverageCost = Boolean(security.has_position) && averageCost > 0;
		const scaleValues = hasAverageCost ? [...values, averageCost] : values;
		return b`<tui-chart
      aria-label="${security.symbol} price history"
      height="6"
      min=${Math.min(...scaleValues)}
      max=${Math.max(...scaleValues)}
      threshold=${hasAverageCost ? averageCost : ""}
      above-variant=${hasAverageCost ? "success" : ""}
      below-variant=${hasAverageCost ? "error" : ""}
      .values=${values}
    ></tui-chart>`;
	}
	renderExpandedRow(security, detailsId) {
		const aliasBusy = this.busyAction === `aliases:${security.symbol}`;
		const multiplier = Number(security.ai_research_multiplier);
		return b`
      <tr id=${detailsId}>
        <td
          colspan=${this.selectedColumns.size + 1}
          style="overflow-wrap: anywhere"
        >
          <tui-box border="single" aria-label="${security.symbol} details">
            ${this.renderPriceChart(security)}
            <table style="width: 100%; border-spacing: 0">
              <tbody>
                ${security.price_warning ? this.renderDetailRow("Warning", b`<tui-text variant="warning"
                          >${security.price_warning}</tui-text
                        >`) : ""}
                ${this.renderDetailRow("Geography", security.geography || "-")}
                ${this.renderDetailRow("Industry", security.industry || "-")}
                ${this.renderDetailRow("Lot", security.min_lot ?? "-")}
                ${this.renderDetailRow("Quantity", security.quantity ?? 0)}
                ${this.renderDetailRow("Price", formatCurrency(security.current_price, security.currency))}
                ${this.renderDetailRow("Aliases", b`<tui-input
                      id="aliases-${safeId(security.symbol)}"
                      aria-label="Aliases for ${security.symbol}"
                      value=${security.aliases ?? ""}
                      size="28"
                    ></tui-input
                    >&nbsp;<tui-button
                      ?disabled=${aliasBusy}
                      @click=${() => this.saveAliases(security)}
                      >Save aliases</tui-button
                    >`)}
                ${this.renderDetailRow("Forecast 4w", this.renderColored(security.forecast_return_4w, scorePercent(security.forecast_return_4w, 1)))}
                ${this.renderDetailRow("Timing", scorePercent(security.forecast_score))}
                ${this.renderDetailRow("AI research", Number.isFinite(multiplier) ? multiplier.toFixed(2) : "-")}
                ${security.ai_research_multiplier_source ? this.renderDetailRow("Source", security.ai_research_multiplier_source) : ""}
                ${security.ai_research_multiplier_updated_at ? this.renderDetailRow("Updated", new Date(security.ai_research_multiplier_updated_at).toLocaleString()) : ""}
                ${security.ai_research_multiplier_analysis ? this.renderDetailRow("Analysis", security.ai_research_multiplier_analysis) : ""}
                ${this.renderDetailRow("Opportunity", scorePercent(security.opp_score, 1))}
                ${this.renderDetailRow("Dip", scorePercent(security.dip_score, 1))}
                ${this.renderDetailRow("Capitulation", scorePercent(security.capitulation_score, 1))}
                ${this.renderDetailRow("Cycle turn", security.cycle_turn ? "yes" : "no")}
                ${this.renderDetailRow("Freefall blocked", security.freefall_block ? "yes" : "no")}
                ${security.recommendation?.reason ? this.renderDetailRow("Plan", security.recommendation.reason) : ""}
                ${this.renderDetailRow("Actions", this.inactiveOnly ? b`<tui-button
                          ?disabled=${this.busyAction === `activate:${security.symbol}`}
                          @click=${() => this.activateSecurity(security)}
                          >Activate</tui-button
                        >&nbsp;<tui-button
                          variant="error"
                          title=${security.can_delete ? "Permanently delete unused security" : `Cannot delete: ${security.transaction_count || 0} historical transaction(s)`}
                          ?disabled=${!security.can_delete}
                          @click=${() => this.openDeleteDialog(security)}
                          >Delete Permanently</tui-button
                        >` : b`<tui-button
                        variant="error"
                        @click=${() => this.openDeleteDialog(security)}
                        >Remove</tui-button
                      >`)}
                ${this.inactiveOnly && !security.can_delete ? this.renderDetailRow("Deletion", `Permanent deletion is unavailable because this security has ${security.transaction_count || 0} historical transaction(s).`) : ""}
              </tbody>
            </table>
          </tui-box>
        </td>
      </tr>
    `;
	}
	renderTable() {
		const visible = this.visibleSecurities;
		const allExpanded = visible.length > 0 && visible.every((security) => this.expandedSymbols.has(security.symbol));
		if (visible.length === 0) return b`<div>No securities match the current controls</div>`;
		return b`
      <div style="width: 100%; min-width: 0; overflow-x: auto">
        <table
          aria-label=${this.inactiveOnly ? "Inactive Securities" : "Securities"}
          style="width: 100%; border-spacing: 0"
        >
          <thead>
            <tr>
            <th scope="col" style="text-align: left; vertical-align: top">
              ${allExpanded ? b`<tui-button
                      aria-label="Collapse all securities"
                      @click=${this.toggleAll}
                      >−</tui-button
                    >` : b`<tui-button
                      aria-label="Expand all securities"
                      @click=${this.toggleAll}
                      >+</tui-button
                    >`}
            </th>
            ${this.columnVisible("price") ? b`<th
                    scope="col"
                    style="text-align: left; vertical-align: top"
                  >
                    <span aria-hidden="true">│&nbsp;</span>Price
                  </th>` : ""}
            ${this.renderSortableHeader("Security", "symbol")}
            ${this.columnVisible("value") ? this.renderSortableHeader("Value", "value") : ""}
            ${this.columnVisible("pnl") ? this.renderSortableHeader("P/L", "pnl") : ""}
            ${this.columnVisible("ideal") ? this.renderSortableHeader("Ideal", "ideal") : ""}
            ${this.columnVisible("plan") ? this.renderSortableHeader("Plan", "recommendation") : ""}
            ${this.columnVisible("trade") ? b`<th
                    scope="col"
                    style="text-align: left; vertical-align: top"
                  >
                    <span aria-hidden="true">│&nbsp;</span
                    >${this.inactiveOnly ? "Status" : "Trade"}
                  </th>` : ""}
            </tr>
          </thead>
          <tbody>
            ${visible.map((security) => this.renderSecurityRow(security))}
          </tbody>
        </table>
      </div>
    `;
	}
	renderColumnsDialog() {
		return b`
      <dialog
        id="columns-dialog"
        aria-label="Choose table columns"
        style="color: var(--tui-color); background: var(--tui-background); border: 0; padding: 0; max-width: calc(100% - 2ch)"
      >
        <tui-box heading="Columns" border="single">
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("price")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "price")}
              >Price</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              checked
              disabled
              aria-label="Security column is always visible"
              >Security</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("value")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "value")}
              >Value</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("pnl")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "pnl")}
              >P/L</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("ideal")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "ideal")}
              >Ideal</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("plan")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "plan")}
              >Plan</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("trade")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "trade")}
              >Trade</tui-toggle
            >
          </div>
          ${this.errorMessage ? b`<div>
                  <tui-text variant="error">${this.errorMessage}</tui-text>
                </div>` : ""}
          <div>
            <tui-button @click=${this.closeColumnsDialog}>Done</tui-button>
          </div>
        </tui-box>
      </dialog>
    `;
	}
	renderAddDialog() {
		return b`
      <dialog
        id="add-security-dialog"
        aria-label="Add Security"
        style="color: var(--tui-color); background: var(--tui-background); border: 0; padding: 0; max-width: calc(100% - 2ch)"
      >
        <tui-box heading="Add Security" border="single">
          <form @submit=${this.addSecurity}>
            <label>
              Symbol&nbsp;<tui-input
                id="add-security-symbol"
                aria-label="TraderNet security symbol"
                placeholder="AAPL.US"
                required
                ?disabled=${this.busyAction === "add"}
              ></tui-input>
            </label>
            <div>
              Geography and industry will be filled by the next metadata sync.
            </div>
            ${this.addError ? b`<div><tui-text variant="error">${this.addError}</tui-text></div>` : ""}
            <div>
              <tui-button type="submit" ?disabled=${this.busyAction === "add"}
                >Add Security</tui-button
              >&nbsp;
              <tui-button
                type="button"
                ?disabled=${this.busyAction === "add"}
                @click=${this.closeAddDialog}
                >Cancel</tui-button
              >
            </div>
          </form>
        </tui-box>
      </dialog>
    `;
	}
	renderDeleteDialog() {
		const security = this.deleteCandidate;
		return b`
      <dialog
        id="delete-security-dialog"
        aria-label=${this.inactiveOnly ? "Delete Security Permanently" : "Remove Security"}
        style="color: var(--tui-color); background: var(--tui-background); border: 0; padding: 0; max-width: calc(100% - 2ch)"
      >
        <tui-box
          heading=${this.inactiveOnly ? "Delete Security Permanently" : "Remove Security"}
          border="single"
        >
          ${security ? b`
                  <div>
                    ${this.inactiveOnly ? `Permanently delete ${security.symbol}?` : `Remove ${security.symbol} from the active universe?`}
                  </div>
                  ${security.has_position ? b`<div>
                          <tui-text variant="warning"
                            >Position: ${security.quantity} shares
                            (${formatCurrency(security.value_eur, "EUR")}). It
                            will remain managed, but new buys will be
                            disabled.</tui-text
                          >
                        </div>` : ""}
                  ${this.errorMessage ? b`<div>
                          <tui-text variant="error"
                            >${this.errorMessage}</tui-text
                          >
                        </div>` : ""}
                  <div>
                    <tui-button
                      variant="error"
                      ?disabled=${this.busyAction === `delete:${security.symbol}`}
                      @click=${this.deleteSecurity}
                      >${this.inactiveOnly ? "Delete Permanently" : "Remove"}</tui-button
                    >&nbsp;
                    <tui-button
                      ?disabled=${this.busyAction === `delete:${security.symbol}`}
                      @click=${this.closeDeleteDialog}
                      >Cancel</tui-button
                    >
                  </div>
                ` : ""}
        </tui-box>
      </dialog>
    `;
	}
	render() {
		let content;
		if (this.securities.loading && !this.securities.value) content = b`<span>Loading securities…</span>`;
		else if (this.securities.error) content = b`<tui-text variant="error"
        >Securities unavailable: ${this.securities.error.message}</tui-text
      >`;
		else content = b`
        ${this.renderControls()} ${this.renderStats()}
        ${this.message ? b`<div><tui-text variant="success">${this.message}</tui-text></div>` : ""}
        ${this.errorMessage ? b`<div><tui-text variant="error">${this.errorMessage}</tui-text></div>` : ""}
        ${this.renderTable()}
      `;
		return b`
      ${this.bare ? content : b`<tui-box
            heading=${this.inactiveOnly ? "Inactive Securities" : "Securities"}
            border="single"
            >${content}</tui-box
          >`}
      ${this.inactiveOnly ? "" : b`${this.renderColumnsDialog()} ${this.renderAddDialog()}`}
      ${this.renderDeleteDialog()}
    `;
	}
};
customElements.define("sentinel-securities", SentinelSecurities);
//#endregion
//#region src/widget-state.js
var STORAGE_KEY = "sentinel.collapsedWidgets";
var DEFAULTS = {
	"inactive-securities": true,
	composition: true,
	"forward-return": true
};
function readState() {
	try {
		const stored = window.localStorage?.getItem(STORAGE_KEY);
		return stored ? {
			...DEFAULTS,
			...JSON.parse(stored)
		} : { ...DEFAULTS };
	} catch {
		return { ...DEFAULTS };
	}
}
function widgetCollapsed(id) {
	return Boolean(readState()[id]);
}
function storeWidgetCollapsed(id, collapsed) {
	try {
		window.localStorage?.setItem(STORAGE_KEY, JSON.stringify({
			...readState(),
			[id]: Boolean(collapsed)
		}));
	} catch {}
}
//#endregion
//#region src/sentinel-inactive-securities.js
var SentinelInactiveSecurities = class extends i {
	static properties = {
		detailsRequested: { state: true },
		period: { state: true }
	};
	constructor() {
		super();
		this.detailsRequested = !widgetCollapsed("inactive-securities");
		this.period = "1Y";
		this.periodChanged = (event) => {
			this.period = event.detail?.period || "1Y";
			const table = this.querySelector("sentinel-securities");
			if (table) {
				table.period = this.period;
				table.securities.refresh();
			}
		};
		this.securityListChanged = (event) => {
			this.summaries.refresh();
			const table = this.querySelector("sentinel-securities");
			if (table && event.target !== table) table.securities.refresh();
		};
	}
	summaries = new LiveResource(this, (signal) => getJson("/api/securities", { signal }), { interval: 6e4 });
	createRenderRoot() {
		return this;
	}
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-security-period-change", this.periodChanged);
		window.addEventListener("sentinel-security-list-change", this.securityListChanged);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-security-period-change", this.periodChanged);
		window.removeEventListener("sentinel-security-list-change", this.securityListChanged);
		super.disconnectedCallback();
	}
	toggleDetails(event) {
		const open = event.currentTarget.open;
		storeWidgetCollapsed("inactive-securities", !open);
		if (open && !this.detailsRequested) this.detailsRequested = true;
	}
	render() {
		if (this.summaries.loading && !this.summaries.value) return "";
		if (this.summaries.error) return "";
		const count = (this.summaries.value || []).filter((security) => !security.active).length;
		if (count === 0) return "";
		return b`
      <details
        ?open=${!widgetCollapsed("inactive-securities")}
        @toggle=${this.toggleDetails}
      >
        <summary style="cursor: pointer; font-weight: 600">
          Inactive Securities (${count})
        </summary>
        ${this.detailsRequested ? b`<tui-box border="single">
              <sentinel-securities
                inactive-only
                bare
                .period=${this.period}
              ></sentinel-securities>
            </tui-box>` : ""}
      </details>
    `;
	}
};
customElements.define("sentinel-inactive-securities", SentinelInactiveSecurities);
//#endregion
//#region src/sentinel-risk-return.js
function clamp01(value) {
	if (!Number.isFinite(value)) return 0;
	return Math.max(0, Math.min(1, value));
}
function percent$1(value, digits = 1) {
	if (value === null || value === void 0 || Number.isNaN(value)) return "—";
	return `${(value * 100).toFixed(digits)}%`;
}
function number(value, digits = 2) {
	if (value === null || value === void 0 || Number.isNaN(value)) return "—";
	return Number(value).toFixed(digits);
}
var SentinelRiskReturn = class extends i {
	composition = new LiveResource(this, (signal) => getJson("/api/portfolio/composition", { signal }), { interval: 3e5 });
	createRenderRoot() {
		return this;
	}
	storeCollapsed(event) {
		storeWidgetCollapsed("risk-return", !event.currentTarget.open);
	}
	metricRows(metrics) {
		const rows = [
			{
				label: "Last year",
				subLabel: "1Y return — money made (or lost) after subtracting deposits",
				value: metrics.return_1y,
				formatted: percent$1(metrics.return_1y),
				min: -.3,
				max: .3,
				reference: 0,
				minLabel: "-30%",
				maxLabel: "+30%",
				referenceLabel: "break-even",
				goodDirection: "high"
			},
			{
				label: "Since the beginning",
				subLabel: `CAGR — annualized growth since first deposit (${number(metrics.inception_years || 0, 1)} years)`,
				value: metrics.return_since_inception_cagr,
				formatted: percent$1(metrics.return_since_inception_cagr),
				min: -.3,
				max: .3,
				reference: 0,
				minLabel: "-30%",
				maxLabel: "+30%",
				referenceLabel: "break-even",
				goodDirection: "high"
			},
			{
				label: "Bumpiness",
				subLabel: "Annual volatility — how wild the daily price swings are",
				value: metrics.volatility,
				formatted: percent$1(metrics.volatility),
				min: 0,
				max: .4,
				reference: .18,
				minLabel: "calm",
				maxLabel: "wild",
				referenceLabel: "typical",
				goodDirection: "low"
			},
			{
				label: "Worst drop",
				subLabel: "Max drawdown — biggest dip from peak to bottom",
				value: metrics.max_drawdown,
				formatted: percent$1(metrics.max_drawdown),
				min: 0,
				max: .5,
				reference: .2,
				minLabel: "no dips",
				maxLabel: "crash",
				referenceLabel: "tolerable",
				goodDirection: "low"
			},
			{
				label: "Reward for the bumps",
				subLabel: "Sharpe ratio — return per unit of risk, vs cash",
				value: metrics.sharpe,
				formatted: number(metrics.sharpe),
				min: -1,
				max: 3,
				reference: 1,
				minLabel: "-1",
				maxLabel: "3",
				referenceLabel: "good",
				goodDirection: "high"
			},
			{
				label: "All in one basket?",
				subLabel: "Concentration (HHI) — 0 spread evenly, 1 single position",
				value: metrics.hhi,
				formatted: number(metrics.hhi, 3),
				min: 0,
				max: 1,
				reference: .1,
				minLabel: "spread",
				maxLabel: "all-in",
				referenceLabel: "diversified",
				goodDirection: "low"
			}
		];
		if ((this.composition.value?.home_markets || []).length > 0 && (metrics.home_coverage_pct || 0) > 0) {
			const coverage = `covers ${percent$1(metrics.home_coverage_pct, 0)} of holdings`;
			rows.push({
				label: "Tracks home markets?",
				subLabel: `Beta vs each holding's own market index, value-weighted (${coverage})`,
				value: metrics.beta_vs_home,
				formatted: number(metrics.beta_vs_home),
				min: -1,
				max: 2,
				reference: 1,
				minLabel: "-1",
				maxLabel: "+2",
				referenceLabel: "in step",
				goodDirection: "neutral"
			}, {
				label: "Beating home markets?",
				subLabel: `Alpha — value-weighted outperformance vs each holding's home index (${coverage})`,
				value: metrics.alpha_1y_vs_home,
				formatted: percent$1(metrics.alpha_1y_vs_home),
				min: -.2,
				max: .2,
				reference: 0,
				minLabel: "-20%",
				maxLabel: "+20%",
				referenceLabel: "matches",
				goodDirection: "high"
			});
		}
		return rows;
	}
	metricColor(row) {
		if (row.goodDirection === "neutral") return "var(--tui-color)";
		return (row.goodDirection === "high" ? row.value >= row.reference : row.value <= row.reference) ? "var(--tui-success-color)" : "var(--tui-error-color)";
	}
	renderMetric(row) {
		const span = row.max - row.min;
		const valuePosition = span > 0 ? clamp01((row.value - row.min) / span) : .5;
		const referencePosition = span > 0 ? clamp01((row.reference - row.min) / span) : .5;
		const color = this.metricColor(row);
		return b`
      <div style="display: grid; gap: 2px">
        <div
          style="display: flex; justify-content: space-between; gap: 1ch; align-items: baseline"
        >
          <div style="flex: 1 1 auto; min-width: 0">
            <div style="font-weight: 600">${row.label}</div>
            <div style="color: var(--tui-disabled-color); font-size: 0.75em">
              ${row.subLabel}
            </div>
          </div>
          <div style="color: ${color}; flex: 0 0 auto; font-weight: 600">
            ${row.formatted}
          </div>
        </div>
        <div
          aria-hidden="true"
          style="position: relative; height: 10px; margin: 4px 0 2px; overflow: hidden; background: color-mix(in srgb, var(--tui-color) 18%, transparent)"
        >
          <div
            style="position: absolute; left: ${Math.min(referencePosition, valuePosition) * 100}%; width: ${Math.abs(valuePosition - referencePosition) * 100}%; top: 0; bottom: 0; background: ${color}"
          ></div>
          <div
            style="position: absolute; left: ${referencePosition * 100}%; top: -2px; bottom: -2px; width: 1px; background: var(--tui-disabled-color); transform: translateX(-0.5px)"
          ></div>
        </div>
        <div
          aria-hidden="true"
          style="position: relative; height: 1.1em; color: var(--tui-disabled-color); font-size: 0.75em"
        >
          <span style="position: absolute; left: 0">${row.minLabel}</span>
          <span
            style="position: absolute; left: ${referencePosition * 100}%; transform: translateX(-50%); white-space: nowrap"
            >${row.referenceLabel}</span
          >
          <span style="position: absolute; right: 0">${row.maxLabel}</span>
        </div>
      </div>
    `;
	}
	renderHomeMarkets(data) {
		const markets = data.home_markets || [];
		if (markets.length === 0 || !(data.metrics.home_coverage_pct > 0)) return b`<div
        style="color: var(--tui-disabled-color); font-size: 0.75em; font-style: italic"
      >
        Benchmarks not yet synced — home-market comparison will populate on
        next sync cycle.
      </div>`;
		return b`
      <div style="display: grid; gap: 2px">
        <div
          style="color: var(--tui-disabled-color); font-size: 0.75em; font-weight: 600; text-transform: uppercase"
        >
          vs home markets
        </div>
        ${markets.map((market) => b`
            <div
              style="display: flex; justify-content: space-between; gap: 1ch; font-size: 0.75em"
            >
              <span style="color: var(--tui-disabled-color)"
                >${market.group} (${percent$1(market.weight_pct, 0)})</span
              >
              <span
                style="color: ${market.alpha_1y >= 0 ? "var(--tui-success-color)" : "var(--tui-error-color)"}"
                >${percent$1(market.alpha_1y)} α · β
                ${number(market.beta)}</span
              >
            </div>
          `)}
      </div>
    `;
	}
	render() {
		const data = this.composition.value;
		if (this.composition.loading && !data || this.composition.error || !data?.metrics) return "";
		return b`
      <details
        ?open=${!widgetCollapsed("risk-return")}
        @toggle=${this.storeCollapsed}
      >
        <summary style="cursor: pointer; font-weight: 600">Risk / Return</summary>
        <tui-box heading="Risk / Return" border="single">
          <div style="display: grid; gap: 1em">
            ${this.metricRows(data.metrics).map((row) => this.renderMetric(row))}
            ${this.renderHomeMarkets(data)}
          </div>
        </tui-box>
      </details>
    `;
	}
};
customElements.define("sentinel-risk-return", SentinelRiskReturn);
//#endregion
//#region src/sentinel-security-allocation.js
function percent(value) {
	return `${Number(value || 0).toFixed(1)}%`;
}
var SentinelSecurityAllocation = class extends i {
	static properties = {
		sortBy: { state: true },
		showIdeal: { state: true },
		compact: { state: true }
	};
	constructor() {
		super();
		this.sortBy = "allocation";
		this.showIdeal = true;
		this.compact = false;
	}
	allocation = new LiveResource(this, async (signal) => {
		const [securities, planner] = await Promise.all([getJson("/api/unified?period=1Y", { signal }), getJson("/api/planner/recommendations", { signal })]);
		return {
			securities,
			planner
		};
	}, { interval: 6e4 });
	createRenderRoot() {
		return this;
	}
	connectedCallback() {
		super.connectedCallback();
		if (typeof ResizeObserver !== "undefined") {
			this.resizeObserver = new ResizeObserver(([entry]) => {
				const compact = entry.contentRect.width <= 520;
				if (compact !== this.compact) this.compact = compact;
			});
			this.resizeObserver.observe(this);
		}
	}
	disconnectedCallback() {
		this.resizeObserver?.disconnect();
		super.disconnectedCallback();
	}
	storeCollapsed(event) {
		storeWidgetCollapsed("security-allocation", !event.currentTarget.open);
	}
	changeSort(event) {
		this.sortBy = event.currentTarget.value;
	}
	changeIdeal(event) {
		this.showIdeal = event.currentTarget.checked;
	}
	get rows() {
		const securities = this.allocation.value?.securities || [];
		const planner = this.allocation.value?.planner || {};
		const recommendations = planner.recommendations || [];
		const longTermPlan = planner.plan;
		const targets = new Map((longTermPlan?.targets || []).map((target) => [target.symbol, target]));
		const rows = securities.filter((security) => {
			const hasPosition = security.has_position && security.value_eur > 0;
			const hasRecommendation = recommendations.some((recommendation) => recommendation.symbol === security.symbol);
			const hasIdeal = this.showIdeal && targets.has(security.symbol);
			return hasPosition || hasRecommendation || hasIdeal;
		}).map((security) => {
			const recommendation = recommendations.find((candidate) => candidate.symbol === security.symbol);
			const delta = recommendation ? recommendation.value_delta_eur : 0;
			const target = targets.get(security.symbol);
			const current = security.value_eur || 0;
			const final = current + delta;
			const ideal = Number(target?.target_value_eur ?? recommendation?.target_value_eur ?? current);
			const modelIdeal = Number(target?.model_target_value_eur ?? ideal);
			if (final <= 0 && current <= 0 && ideal <= 0) return;
			return {
				symbol: security.symbol,
				current,
				final: Math.max(0, final),
				delta,
				ideal,
				currentAllocation: security.current_allocation || 0,
				postPlanAllocation: security.post_plan_allocation ?? security.current_allocation ?? 0,
				idealAllocation: target?.target_allocation_pct ?? security.ideal_allocation ?? 0,
				targetGap: Number(target?.gap_eur || 0),
				quantityDelta: Number(target?.quantity_delta || 0),
				modelIdeal,
				sellLocked: Boolean(target?.sell_locked),
				isBuy: delta > 0,
				isSell: delta < 0,
				maxBar: this.showIdeal ? Math.max(current, final, ideal) : Math.max(current, final)
			};
		}).filter(Boolean);
		const currentCash = Number(longTermPlan?.current_cash_eur || 0);
		const targetCash = Number(longTermPlan?.target_cash_value_eur || 0);
		if (currentCash > 0 || targetCash > 0) {
			const currentTotal = Number(longTermPlan?.current_total_value_eur || 0);
			const plannedCash = Number.isFinite(Number(planner.summary?.cash_after_plan)) ? Math.max(0, Number(planner.summary.cash_after_plan)) : currentCash;
			const delta = plannedCash - currentCash;
			rows.push({
				symbol: "CASH",
				current: currentCash,
				final: plannedCash,
				delta,
				ideal: targetCash,
				currentAllocation: currentTotal > 0 ? currentCash / currentTotal * 100 : 0,
				postPlanAllocation: currentTotal > 0 ? plannedCash / currentTotal * 100 : 0,
				idealAllocation: Number(longTermPlan?.target_cash_allocation_pct || 0),
				targetGap: Number(longTermPlan?.cash_gap_eur || 0),
				quantityDelta: 0,
				modelIdeal: targetCash,
				sellLocked: false,
				isBuy: delta > 0,
				isSell: delta < 0,
				maxBar: this.showIdeal ? Math.max(currentCash, plannedCash, targetCash) : Math.max(currentCash, plannedCash)
			});
		}
		rows.sort((left, right) => this.sortBy === "ideal" ? right.ideal - left.ideal : Math.max(right.final, right.current) - Math.max(left.final, left.current));
		return rows;
	}
	renderRow(row, maximum) {
		const grayWidth = maximum > 0 ? (row.isBuy ? row.final - row.delta : row.final) / maximum * 100 : 0;
		const deltaWidth = maximum > 0 ? Math.abs(row.delta) / maximum * 100 : 0;
		const idealPosition = maximum > 0 ? row.ideal / maximum * 100 : 0;
		const targetGapText = `${row.targetGap >= 0 ? "+" : "-"}${formatCurrency(Math.abs(row.targetGap), "EUR")}`;
		const quantityText = Math.abs(row.quantityDelta || 0) > 1e-4 ? `; ${row.quantityDelta > 0 ? "+" : "-"}${Math.abs(row.quantityDelta).toLocaleString()} shares` : "";
		const idealTitle = row.sellLocked ? `No-sell holding remains unchanged; model target: ${formatCurrency(row.modelIdeal, "EUR")}` : `12-month target: ${formatCurrency(row.ideal, "EUR")}; gap: ${targetGapText}${quantityText}`;
		return b`
      <tr>
        <td
          title=${row.symbol}
          style="width: ${this.compact ? "62px" : "76px"}; padding: 4px 8px 4px 0; font-size: 0.75em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis"
        >
          ${row.symbol}
        </td>
        <td style="width: 100%; padding: 4px 8px 4px 0">
          <div
            style="position: relative; display: flex; width: 100%; height: 16px; overflow: hidden; background: color-mix(in srgb, var(--tui-color) 8%, transparent); border: 1px solid color-mix(in srgb, var(--tui-color) 30%, transparent)"
          >
            ${grayWidth > 0 ? b`<div
                  style="height: 100%; width: ${grayWidth}%; background: var(--tui-disabled-color)"
                ></div>` : ""}
            ${row.isBuy && deltaWidth > 0 ? b`<div
                  style="height: 100%; width: ${deltaWidth}%; background: var(--tui-success-color)"
                ></div>` : ""}
            ${row.isSell && deltaWidth > 0 ? b`<div
                  style="height: 100%; width: ${deltaWidth}%; background: var(--tui-error-color)"
                ></div>` : ""}
            ${this.showIdeal ? b`<div
                  title=${idealTitle}
                  style="position: absolute; left: ${idealPosition}%; top: -2px; bottom: -2px; width: 2px; background: light-dark(blue, deepskyblue); transform: translateX(-1px)"
                ></div>` : ""}
          </div>
        </td>
        <td
          style="width: ${this.compact ? "118px" : "174px"}; padding: 4px 0; color: var(--tui-disabled-color); font-size: 0.6875em; text-align: right; white-space: ${this.compact ? "normal" : "nowrap"}"
        >
          ${this.compact ? "" : b`<div>
                <span>${percent(row.currentAllocation)}</span>
                <span style="padding: 0 4px">→</span>
                <span
                  style="color: ${row.isBuy ? "var(--tui-success-color)" : row.isSell ? "var(--tui-error-color)" : "inherit"}; font-weight: ${row.isBuy || row.isSell ? "600" : "inherit"}"
                  >${percent(row.postPlanAllocation)}</span
                >
                <span style="padding-left: 4px; color: light-dark(blue, deepskyblue)"
                  >/ ${percent(row.idealAllocation)}</span
                >
              </div>`}
          <div
            style="margin-top: 2px; color: var(--tui-disabled-color); font-size: ${this.compact ? "0.82em" : "0.91em"}"
          >
            ${formatCurrency(row.ideal, "EUR")} ·
            ${row.sellLocked ? "unchanged" : targetGapText}
          </div>
        </td>
      </tr>
    `;
	}
	legend(color, label, ideal = false) {
		return b`<span
      style="display: inline-flex; align-items: center; gap: 0.5ch; white-space: nowrap"
    >
      <span
        aria-hidden="true"
        style="display: inline-block; flex: 0 0 auto; width: ${ideal ? "2px" : "12px"}; height: ${ideal ? "12px" : "10px"}; background: ${color}; border: ${ideal ? "none" : "1px solid color-mix(in srgb, var(--tui-color) 30%, transparent)"}"
      ></span>
      <span style="color: var(--tui-disabled-color); font-size: 0.75em"
        >${label}</span
      >
    </span>`;
	}
	render() {
		if (this.allocation.loading && !this.allocation.value || this.allocation.error || !this.allocation.value) return "";
		const rows = this.rows;
		const maximum = Math.max(...rows.map((row) => row.maxBar), 0);
		return b`
      <details
        ?open=${!widgetCollapsed("security-allocation")}
        @toggle=${this.storeCollapsed}
      >
        <summary style="cursor: pointer; font-weight: 600">
          Security Allocation
        </summary>
        <tui-box heading="Security Allocation" border="single">
          <div style="display: grid; gap: 0.75em">
            <div
              style="display: flex; justify-content: space-between; align-items: baseline; gap: 1ch; flex-wrap: wrap"
            >
              <span
                style="color: var(--tui-disabled-color); font-size: 0.75em; font-weight: 600; text-transform: uppercase"
                >Security Allocation</span
              >
              <span style="display: inline-flex; gap: 1ch; align-items: baseline">
                <tui-radio-buttonset
                  aria-label="Security allocation sorting"
                  value=${this.sortBy}
                  @change=${this.changeSort}
                >
                  <tui-radio-button value="allocation"
                    >By allocation</tui-radio-button
                  >
                  <tui-radio-button value="ideal">By ideal</tui-radio-button>
                </tui-radio-buttonset>
                <tui-toggle
                  ?checked=${this.showIdeal}
                  @change=${this.changeIdeal}
                  >Ideal</tui-toggle
                >
              </span>
            </div>
            ${rows.length > 0 ? b`<div style="min-width: 0; overflow-x: auto">
                  <table
                    aria-label="Security Allocation"
                    style="width: 100%; border-collapse: collapse; table-layout: ${this.compact ? "auto" : "fixed"}"
                  >
                    <tbody>
                      ${rows.map((row) => this.renderRow(row, maximum))}
                    </tbody>
                  </table>
                </div>` : b`<div
                  style="padding: 2em 0; color: var(--tui-disabled-color); text-align: center"
                >
                  No allocation data available
                </div>`}
            <div
              style="display: flex; gap: 1em; flex-wrap: wrap; padding-top: 4px"
            >
              ${this.legend("var(--tui-disabled-color)", "Current holding")}
              ${this.legend("var(--tui-success-color)", "Today's increase")}
              ${this.legend("var(--tui-error-color)", "Today's decrease")}
              ${this.showIdeal ? this.legend("light-dark(blue, deepskyblue)", "12-month target", true) : ""}
            </div>
          </div>
        </tui-box>
      </details>
    `;
	}
};
customElements.define("sentinel-security-allocation", SentinelSecurityAllocation);
//#endregion
//#region src/sentinel-status-bar.js
var SentinelStatusBar = class extends i {
	static properties = {
		selectedMode: { state: true },
		modePending: { state: true }
	};
	constructor() {
		super();
		this.selectedMode = void 0;
		this.modePending = false;
	}
	version = new LiveResource(this, (signal) => getJson("/api/version", { signal }), { interval: 0 });
	health = new LiveResource(this, (signal) => getJson("/api/health", { signal }), { interval: 3e4 });
	markets = new LiveResource(this, (signal) => getJson("/api/markets/status", { signal }), { interval: 6e4 });
	refreshHealth = () => this.health.refresh();
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-setting-changed", this.refreshHealth);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-setting-changed", this.refreshHealth);
		super.disconnectedCallback();
	}
	createRenderRoot() {
		return this;
	}
	get versionText() {
		return this.version.value?.version ?? "version unavailable";
	}
	renderBrokerStatus() {
		if (this.health.error) return b`<tui-text variant="error">broker: unavailable</tui-text>`;
		if (!this.health.value) return b`<span>broker: connecting</span>`;
		return this.health.value.broker_connected ? b`<tui-text variant="success">broker: connected</tui-text>` : b`<tui-text variant="error">broker: disconnected</tui-text>`;
	}
	renderMarkets() {
		if (this.markets.error || this.markets.value?.markets?.length === 0) return b`<tui-text variant="error">markets unavailable</tui-text>`;
		if (!this.markets.value) return b`<span>markets loading</span>`;
		return this.markets.value.markets.map((market, index) => b`
        ${index > 0 ? b`<span aria-hidden="true">&nbsp;</span>` : ""}
        <tui-text variant=${market.is_open ? "success" : "error"}
          >${market.name}</tui-text
        >
      `);
	}
	updated() {
		const backendMode = this.health.value?.trading_mode;
		if (!this.modePending && backendMode && backendMode !== this.selectedMode) this.selectedMode = backendMode;
	}
	async changeMode(event) {
		const previousMode = this.health.value?.trading_mode;
		this.selectedMode = event.currentTarget.value;
		this.modePending = true;
		try {
			await putJson("/api/settings/trading_mode", { value: this.selectedMode });
			await this.health.refresh();
		} catch (error) {
			this.selectedMode = previousMode;
			console.error("Unable to update trading mode", error);
		} finally {
			this.modePending = false;
		}
	}
	render() {
		return b`
      <footer>
        <tui-bar>
          <tui-flex align="baseline" justify="between" wrap>
            <span>Sentinel ${this.versionText}</span>
            <tui-flex align="baseline" wrap>
              <tui-radio-buttonset
                aria-label="Trading mode"
                value=${this.selectedMode ?? this.health.value?.trading_mode ?? "research"}
                ?disabled=${this.modePending}
                inverted
                @change=${this.changeMode}
              >
                <tui-radio-button value="research">Research</tui-radio-button>
                <tui-radio-button value="live">Live</tui-radio-button>
              </tui-radio-buttonset>
              <span aria-hidden="true">&nbsp;│&nbsp;</span>
              ${this.renderBrokerStatus()}
              <span aria-hidden="true">&nbsp;│&nbsp;</span>
              ${this.renderMarkets()}
            </tui-flex>
          </tui-flex>
        </tui-bar>
      </footer>
    `;
	}
};
customElements.define("sentinel-status-bar", SentinelStatusBar);
//#endregion
//#region src/sentinel-app.js
var SentinelApp = class extends i {
	createRenderRoot() {
		return this;
	}
	render() {
		return b`
      <tui-flex direction="column" style="height: 100dvh; overflow: hidden">
        <sentinel-header
          style="display: block; flex: 0 0 auto"
        ></sentinel-header>
        <main style="flex: 1 1 auto; min-height: 0; overflow: auto">
          <sentinel-portfolio-status
            style="display: block"
          ></sentinel-portfolio-status>
          <div aria-hidden="true">&nbsp;</div>
          <sentinel-planner-status
            style="display: block"
          ></sentinel-planner-status>
          <sentinel-portfolio-value
            style="display: block"
          ></sentinel-portfolio-value>
          <sentinel-portfolio-pnl
            style="display: block"
          ></sentinel-portfolio-pnl>
          <sentinel-securities style="display: block"></sentinel-securities>
          <sentinel-inactive-securities
            style="display: block"
          ></sentinel-inactive-securities>
          <sentinel-risk-return style="display: block"></sentinel-risk-return>
          <sentinel-security-allocation
            style="display: block"
          ></sentinel-security-allocation>
        </main>
        <sentinel-status-bar
          style="display: block; flex: 0 0 auto"
        ></sentinel-status-bar>
      </tui-flex>
    `;
	}
};
customElements.define("sentinel-app", SentinelApp);
//#endregion
export { __vitePreload as t };
