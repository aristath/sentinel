const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/dist-B1JDGwcL.js","assets/dist-BiurrlE2.js","assets/dist-BvVii4ez.js","assets/rolldown-runtime-D8jQpDG7.js","assets/dist-DgQIi_yG.js","assets/dist-DbxUlS_P.js","assets/dist-DS9RNkCr.js","assets/dist-Cxm9BCu7.js","assets/dist-Bpa0zahV.js","assets/dist-xbAbliKN.js","assets/dist-CLrlL5Nl.js","assets/dist-Wk6qF9fK.js"])))=>i.map(i=>d[i]);
// \0vite/modulepreload-polyfill.js
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
// node_modules/@lit/reactive-element/css-tag.js
/**
* @license
* Copyright 2019 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var t$4 = globalThis;
var e$9 = t$4.ShadowRoot && (void 0 === t$4.ShadyCSS || t$4.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype;
var s$3 = Symbol();
var o$7 = /* @__PURE__ */ new WeakMap();
var n$5 = class {
	constructor(t, e, o) {
		if (this._$cssResult$ = !0, o !== s$3) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
		this.cssText = t, this.t = e;
	}
	get styleSheet() {
		let t = this.o;
		const s = this.t;
		if (e$9 && void 0 === t) {
			const e = void 0 !== s && 1 === s.length;
			e && (t = o$7.get(s)), void 0 === t && ((this.o = t = new CSSStyleSheet()).replaceSync(this.cssText), e && o$7.set(s, t));
		}
		return t;
	}
	toString() {
		return this.cssText;
	}
};
var r$6 = (t) => new n$5("string" == typeof t ? t : t + "", void 0, s$3);
var i$7 = (t, ...e) => {
	return new n$5(1 === t.length ? t[0] : e.reduce((e, s, o) => e + ((t) => {
		if (!0 === t._$cssResult$) return t.cssText;
		if ("number" == typeof t) return t;
		throw Error("Value passed to 'css' function must be a 'css' function result: " + t + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
	})(s) + t[o + 1], t[0]), t, s$3);
};
var S$1 = (s, o) => {
	if (e$9) s.adoptedStyleSheets = o.map((t) => t instanceof CSSStyleSheet ? t : t.styleSheet);
	else for (const e of o) {
		const o = document.createElement("style"), n = t$4.litNonce;
		void 0 !== n && o.setAttribute("nonce", n), o.textContent = e.cssText, s.appendChild(o);
	}
};
var c$5 = e$9 ? (t) => t : (t) => t instanceof CSSStyleSheet ? ((t) => {
	let e = "";
	for (const s of t.cssRules) e += s.cssText;
	return r$6(e);
})(t) : t;
// node_modules/@lit/reactive-element/reactive-element.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var { is: i$6, defineProperty: e$8, getOwnPropertyDescriptor: h$2, getOwnPropertyNames: r$5, getOwnPropertySymbols: o$6, getPrototypeOf: n$4 } = Object, a$2 = globalThis, c$4 = a$2.trustedTypes, l$4 = c$4 ? c$4.emptyScript : "", p$2 = a$2.reactiveElementPolyfillSupport, d$2 = (t, s) => t, u$4 = {
	toAttribute(t, s) {
		switch (s) {
			case Boolean:
				t = t ? l$4 : null;
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
}, f$2 = (t, s) => !i$6(t, s), b$1 = {
	attribute: !0,
	type: String,
	converter: u$4,
	reflect: !1,
	useDefault: !1,
	hasChanged: f$2
};
Symbol.metadata ??= Symbol("metadata"), a$2.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
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
			void 0 !== h && e$8(this.prototype, t, h);
		}
	}
	static getPropertyDescriptor(t, s, i) {
		const { get: e, set: r } = h$2(this.prototype, t) ?? {
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
		if (this.hasOwnProperty(d$2("elementProperties"))) return;
		const t = n$4(this);
		t.finalize(), void 0 !== t.l && (this.l = [...t.l]), this.elementProperties = new Map(t.elementProperties);
	}
	static finalize() {
		if (this.hasOwnProperty(d$2("finalized"))) return;
		if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(d$2("properties"))) {
			const t = this.properties, s = [...r$5(t), ...o$6(t)];
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
			for (const s of e) i.unshift(c$5(s));
		} else void 0 !== s && i.push(c$5(s));
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
			const h = (void 0 !== i.converter?.toAttribute ? i.converter : u$4).toAttribute(s, i.type);
			this._$Em = t, null == h ? this.removeAttribute(e) : this.setAttribute(e, h), this._$Em = null;
		}
	}
	_$AK(t, s) {
		const i = this.constructor, e = i._$Eh.get(t);
		if (void 0 !== e && this._$Em !== e) {
			const t = i.getPropertyOptions(e), h = "function" == typeof t.converter ? { fromAttribute: t.converter } : void 0 !== t.converter?.fromAttribute ? t.converter : u$4;
			this._$Em = e;
			const r = h.fromAttribute(s, t.type);
			this[e] = r ?? this._$Ej?.get(e) ?? r, this._$Em = null;
		}
	}
	requestUpdate(t, s, i, e = !1, h) {
		if (void 0 !== t) {
			const r = this.constructor;
			if (!1 === e && (h = this[t]), i ??= r.getPropertyOptions(t), !((i.hasChanged ?? f$2)(h, s) || i.useDefault && i.reflect && h === this._$Ej?.get(t) && !this.hasAttribute(r._$Eu(t, i)))) return;
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
y$1.elementStyles = [], y$1.shadowRootOptions = { mode: "open" }, y$1[d$2("elementProperties")] = /* @__PURE__ */ new Map(), y$1[d$2("finalized")] = /* @__PURE__ */ new Map(), p$2?.({ ReactiveElement: y$1 }), (a$2.reactiveElementVersions ??= []).push("2.1.2");
// node_modules/lit-html/lit-html.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var t$3 = globalThis;
var i$5 = (t) => t;
var s$2 = t$3.trustedTypes;
var e$7 = s$2 ? s$2.createPolicy("lit-html", { createHTML: (t) => t }) : void 0;
var h$1 = "$lit$";
var o$5 = `lit$${Math.random().toFixed(9).slice(2)}$`;
var n$3 = "?" + o$5;
var r$4 = `<${n$3}>`;
var l$3 = document;
var c$3 = () => l$3.createComment("");
var a$1 = (t) => null === t || "object" != typeof t && "function" != typeof t;
var u$3 = Array.isArray;
var d$1 = (t) => u$3(t) || "function" == typeof t?.[Symbol.iterator];
var f$1 = "[ 	\n\f\r]";
var v$1 = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g;
var _ = /-->/g;
var m$1 = />/g;
var p$1 = RegExp(`>|${f$1}(?:([^\\s"'>=/]+)(${f$1}*=${f$1}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`, "g");
var g = /'/g;
var $$1 = /"/g;
var y = /^(?:script|style|textarea|title)$/i;
var x = (t) => (i, ...s) => ({
	_$litType$: t,
	strings: i,
	values: s
});
var b = x(1);
var w = x(2);
var E = Symbol.for("lit-noChange");
var A = Symbol.for("lit-nothing");
var C = /* @__PURE__ */ new WeakMap();
var P = l$3.createTreeWalker(l$3, 129);
function V(t, i) {
	if (!u$3(t) || !t.hasOwnProperty("raw")) throw Error("invalid template strings array");
	return void 0 !== e$7 ? e$7.createHTML(i) : i;
}
var N = (t, i) => {
	const s = t.length - 1, e = [];
	let n, l = 2 === i ? "<svg>" : 3 === i ? "<math>" : "", c = v$1;
	for (let i = 0; i < s; i++) {
		const s = t[i];
		let a, u, d = -1, f = 0;
		for (; f < s.length && (c.lastIndex = f, u = c.exec(s), null !== u);) f = c.lastIndex, c === v$1 ? "!--" === u[1] ? c = _ : void 0 !== u[1] ? c = m$1 : void 0 !== u[2] ? (y.test(u[2]) && (n = RegExp("</" + u[2], "g")), c = p$1) : void 0 !== u[3] && (c = p$1) : c === p$1 ? ">" === u[0] ? (c = n ?? v$1, d = -1) : void 0 === u[1] ? d = -2 : (d = c.lastIndex - u[2].length, a = u[1], c = void 0 === u[3] ? p$1 : "\"" === u[3] ? $$1 : g) : c === $$1 || c === g ? c = p$1 : c === _ || c === m$1 ? c = v$1 : (c = p$1, n = void 0);
		const x = c === p$1 && t[i + 1].startsWith("/>") ? " " : "";
		l += c === v$1 ? s + r$4 : d >= 0 ? (e.push(a), s.slice(0, d) + h$1 + s.slice(d) + o$5 + x) : s + o$5 + (-2 === d ? i : x);
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
				if (r.hasAttributes()) for (const t of r.getAttributeNames()) if (t.endsWith(h$1)) {
					const i = v[a++], s = r.getAttribute(t).split(o$5), e = /([.?@])?(.*)/.exec(i);
					d.push({
						type: 1,
						index: l,
						name: e[2],
						strings: s,
						ctor: "." === e[1] ? I : "?" === e[1] ? L : "@" === e[1] ? z : H
					}), r.removeAttribute(t);
				} else t.startsWith(o$5) && (d.push({
					type: 6,
					index: l
				}), r.removeAttribute(t));
				if (y.test(r.tagName)) {
					const t = r.textContent.split(o$5), i = t.length - 1;
					if (i > 0) {
						r.textContent = s$2 ? s$2.emptyScript : "";
						for (let s = 0; s < i; s++) r.append(t[s], c$3()), P.nextNode(), d.push({
							type: 2,
							index: ++l
						});
						r.append(t[i], c$3());
					}
				}
			} else if (8 === r.nodeType) if (r.data === n$3) d.push({
				type: 2,
				index: l
			});
			else {
				let t = -1;
				for (; -1 !== (t = r.data.indexOf(o$5, t + 1));) d.push({
					type: 7,
					index: l
				}), t += o$5.length - 1;
			}
			l++;
		}
	}
	static createElement(t, i) {
		const s = l$3.createElement("template");
		return s.innerHTML = t, s;
	}
};
function M$1(t, i, s = t, e) {
	if (i === E) return i;
	let h = void 0 !== e ? s._$Co?.[e] : s._$Cl;
	const o = a$1(i) ? void 0 : i._$litDirective$;
	return h?.constructor !== o && (h?._$AO?.(!1), void 0 === o ? h = void 0 : (h = new o(t), h._$AT(t, s, e)), void 0 !== e ? (s._$Co ??= [])[e] = h : s._$Cl = h), void 0 !== h && (i = M$1(t, h._$AS(t, i.values), h, e)), i;
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
		const { el: { content: i }, parts: s } = this._$AD, e = (t?.creationScope ?? l$3).importNode(i, !0);
		P.currentNode = e;
		let h = P.nextNode(), o = 0, n = 0, r = s[0];
		for (; void 0 !== r;) {
			if (o === r.index) {
				let i;
				2 === r.type ? i = new k(h, h.nextSibling, this, t) : 1 === r.type ? i = new r.ctor(h, r.name, r.strings, this, t) : 6 === r.type && (i = new Z(h, this, t)), this._$AV.push(i), r = s[++n];
			}
			o !== r?.index && (h = P.nextNode(), o++);
		}
		return P.currentNode = l$3, e;
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
		t = M$1(this, t, i), a$1(t) ? t === A || null == t || "" === t ? (this._$AH !== A && this._$AR(), this._$AH = A) : t !== this._$AH && t !== E && this._(t) : void 0 !== t._$litType$ ? this.$(t) : void 0 !== t.nodeType ? this.T(t) : d$1(t) ? this.k(t) : this._(t);
	}
	O(t) {
		return this._$AA.parentNode.insertBefore(t, this._$AB);
	}
	T(t) {
		this._$AH !== t && (this._$AR(), this._$AH = this.O(t));
	}
	_(t) {
		this._$AH !== A && a$1(this._$AH) ? this._$AA.nextSibling.data = t : this.T(l$3.createTextNode(t)), this._$AH = t;
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
		u$3(this._$AH) || (this._$AH = [], this._$AR());
		const i = this._$AH;
		let s, e = 0;
		for (const h of t) e === i.length ? i.push(s = new k(this.O(c$3()), this.O(c$3()), this, this.options)) : s = i[e], s._$AI(h), e++;
		e < i.length && (this._$AR(s && s._$AB.nextSibling, e), i.length = e);
	}
	_$AR(t = this._$AA.nextSibling, s) {
		for (this._$AP?.(!1, !0, s); t !== this._$AB;) {
			const s = i$5(t).nextSibling;
			i$5(t).remove(), t = s;
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
		if (void 0 === h) t = M$1(this, t, i, 0), o = !a$1(t) || t !== this._$AH && t !== E, o && (this._$AH = t);
		else {
			const e = t;
			let n, r;
			for (t = h[0], n = 0; n < h.length - 1; n++) r = M$1(this, e[s + n], i, n), r === E && (r = this._$AH[n]), o ||= !a$1(r) || r !== this._$AH[n], r === A ? t = A : t !== A && (t += (r ?? "") + h[n + 1]), this._$AH[n] = r;
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
		if ((t = M$1(this, t, i, 0) ?? A) === E) return;
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
		M$1(this, t);
	}
};
var j$1 = {
	M: h$1,
	P: o$5,
	A: n$3,
	C: 1,
	L: N,
	R,
	D: d$1,
	V: M$1,
	I: k,
	H,
	N: L,
	U: z,
	B: I,
	F: Z
};
var B = t$3.litHtmlPolyfillSupport;
B?.(S, k), (t$3.litHtmlVersions ??= []).push("3.3.3");
var D = (t, i, s) => {
	const e = s?.renderBefore ?? i;
	let h = e._$litPart$;
	if (void 0 === h) {
		const t = s?.renderBefore ?? null;
		e._$litPart$ = h = new k(i.insertBefore(c$3(), t), t, void 0, s ?? {});
	}
	return h._$AI(t), h;
};
// node_modules/lit-element/lit-element.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var s$1 = globalThis;
var i$4 = class extends y$1 {
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
i$4._$litElement$ = !0, i$4["finalized"] = !0, s$1.litElementHydrateSupport?.({ LitElement: i$4 });
var o$4 = s$1.litElementPolyfillSupport;
o$4?.({ LitElement: i$4 });
(s$1.litElementVersions ??= []).push("4.2.2");
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.XNTP7DEQ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var variants_styles_default = i$7`
  :where(:root),
  .wa-neutral,
  :host([variant='neutral']) {
    --wa-color-fill-loud: var(--wa-color-neutral-fill-loud);
    --wa-color-fill-normal: var(--wa-color-neutral-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-neutral-fill-quiet);
    --wa-color-border-loud: var(--wa-color-neutral-border-loud);
    --wa-color-border-normal: var(--wa-color-neutral-border-normal);
    --wa-color-border-quiet: var(--wa-color-neutral-border-quiet);
    --wa-color-on-loud: var(--wa-color-neutral-on-loud);
    --wa-color-on-normal: var(--wa-color-neutral-on-normal);
    --wa-color-on-quiet: var(--wa-color-neutral-on-quiet);
  }

  .wa-brand,
  :host([variant='brand']) {
    --wa-color-fill-loud: var(--wa-color-brand-fill-loud);
    --wa-color-fill-normal: var(--wa-color-brand-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-brand-fill-quiet);
    --wa-color-border-loud: var(--wa-color-brand-border-loud);
    --wa-color-border-normal: var(--wa-color-brand-border-normal);
    --wa-color-border-quiet: var(--wa-color-brand-border-quiet);
    --wa-color-on-loud: var(--wa-color-brand-on-loud);
    --wa-color-on-normal: var(--wa-color-brand-on-normal);
    --wa-color-on-quiet: var(--wa-color-brand-on-quiet);
  }

  .wa-success,
  :host([variant='success']) {
    --wa-color-fill-loud: var(--wa-color-success-fill-loud);
    --wa-color-fill-normal: var(--wa-color-success-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-success-fill-quiet);
    --wa-color-border-loud: var(--wa-color-success-border-loud);
    --wa-color-border-normal: var(--wa-color-success-border-normal);
    --wa-color-border-quiet: var(--wa-color-success-border-quiet);
    --wa-color-on-loud: var(--wa-color-success-on-loud);
    --wa-color-on-normal: var(--wa-color-success-on-normal);
    --wa-color-on-quiet: var(--wa-color-success-on-quiet);
  }

  .wa-warning,
  :host([variant='warning']) {
    --wa-color-fill-loud: var(--wa-color-warning-fill-loud);
    --wa-color-fill-normal: var(--wa-color-warning-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-warning-fill-quiet);
    --wa-color-border-loud: var(--wa-color-warning-border-loud);
    --wa-color-border-normal: var(--wa-color-warning-border-normal);
    --wa-color-border-quiet: var(--wa-color-warning-border-quiet);
    --wa-color-on-loud: var(--wa-color-warning-on-loud);
    --wa-color-on-normal: var(--wa-color-warning-on-normal);
    --wa-color-on-quiet: var(--wa-color-warning-on-quiet);
  }

  .wa-danger,
  :host([variant='danger']) {
    --wa-color-fill-loud: var(--wa-color-danger-fill-loud);
    --wa-color-fill-normal: var(--wa-color-danger-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-danger-fill-quiet);
    --wa-color-border-loud: var(--wa-color-danger-border-loud);
    --wa-color-border-normal: var(--wa-color-danger-border-normal);
    --wa-color-border-quiet: var(--wa-color-danger-border-quiet);
    --wa-color-on-loud: var(--wa-color-danger-on-loud);
    --wa-color-on-normal: var(--wa-color-danger-on-normal);
    --wa-color-on-quiet: var(--wa-color-danger-on-quiet);
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.SUWP4C7R.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var badge_styles_default = i$7`
  :host {
    --pulse-color: var(--wa-color-fill-loud, var(--wa-color-brand-fill-loud));

    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.375em 0.625em;
    color: var(--wa-color-on-loud, var(--wa-color-brand-on-loud));
    font-size: max(var(--wa-font-size-3xs), 0.75em);
    font-weight: var(--wa-font-weight-semibold);
    line-height: 1;
    vertical-align: middle;
    white-space: nowrap;
    background-color: var(--wa-color-fill-loud, var(--wa-color-brand-fill-loud));
    border-color: transparent;
    border-radius: var(--wa-border-radius-s);
    border-style: var(--wa-border-style);
    border-width: var(--wa-border-width-s);
    user-select: none;
    -webkit-user-select: none;
    cursor: inherit;

    min-width: 1.25em; /* <-- this is what Safari respects for intrinsic */
    min-height: 1em;
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) {
    --pulse-color: var(--wa-color-border-loud, var(--wa-color-brand-border-loud));

    color: var(--wa-color-on-quiet, var(--wa-color-brand-on-quiet));
    background-color: transparent;
    border-color: var(--wa-color-border-loud, var(--wa-color-brand-border-loud));
  }

  :host([appearance='filled']) {
    --pulse-color: var(--wa-color-fill-normal, var(--wa-color-brand-fill-normal));

    color: var(--wa-color-on-normal, var(--wa-color-brand-on-normal));
    background-color: var(--wa-color-fill-normal, var(--wa-color-brand-fill-normal));
    border-color: transparent;
  }

  :host([appearance='filled-outlined']) {
    --pulse-color: var(--wa-color-border-normal, var(--wa-color-brand-border-normal));

    color: var(--wa-color-on-normal, var(--wa-color-brand-on-normal));
    background-color: var(--wa-color-fill-normal, var(--wa-color-brand-fill-normal));
    border-color: var(--wa-color-border-normal, var(--wa-color-brand-border-normal));
  }

  :host([appearance='accent']) {
    --pulse-color: var(--wa-color-fill-loud, var(--wa-color-brand-fill-loud));

    color: var(--wa-color-on-loud, var(--wa-color-brand-on-loud));
    background-color: var(--wa-color-fill-loud, var(--wa-color-brand-fill-loud));
    border-color: transparent;
  }

  /* Pill modifier */
  :host([pill]) {
    border-radius: var(--wa-border-radius-pill);
  }

  /* Pulse attention */
  :host([attention='pulse']) {
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0% {
      box-shadow: 0 0 0 0 var(--pulse-color);
    }
    70% {
      box-shadow: 0 0 0 0.5rem transparent;
    }
    100% {
      box-shadow: 0 0 0 0 transparent;
    }
  }

  /* Bounce attention */
  :host([attention='bounce']) {
    animation: bounce 1s cubic-bezier(0.28, 0.84, 0.42, 1) infinite;
  }

  @keyframes bounce {
    0%,
    20%,
    50%,
    80%,
    100% {
      transform: translateY(0);
    }
    40% {
      transform: translateY(-5px);
    }
    60% {
      transform: translateY(-2px);
    }
  }

  /* Prevents vertical space when icons with vertical-align are slotted in - https://github.com/shoelace-style/webawesome/issues/2280 */
  [part='start'],
  [part='end'] {
    line-height: 0;
  }

  slot[name='start']::slotted(*) {
    margin-inline-end: 0.375em;
  }

  slot[name='end']::slotted(*) {
    margin-inline-start: 0.375em;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.7VGCIHDG.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __typeError = (msg) => {
	throw TypeError(msg);
};
var __decorateClass = (decorators, target, key, kind) => {
	var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc(target, key) : target;
	for (var i = decorators.length - 1, decorator; i >= 0; i--) if (decorator = decorators[i]) result = (kind ? decorator(target, key, result) : decorator(result)) || result;
	if (kind && result) __defProp(target, key, result);
	return result;
};
var __accessCheck = (obj, member, msg) => member.has(obj) || __typeError("Cannot " + msg);
var __privateGet = (obj, member, getter) => (__accessCheck(obj, member, "read from private field"), getter ? getter.call(obj) : member.get(obj));
var __privateAdd = (obj, member, value) => member.has(obj) ? __typeError("Cannot add the same private member more than once") : member instanceof WeakSet ? member.add(obj) : member.set(obj, value);
var __privateSet = (obj, member, value, setter) => (__accessCheck(obj, member, "write to private field"), setter ? setter.call(obj, value) : member.set(obj, value), value);
// node_modules/@lit/reactive-element/decorators/custom-element.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var t$2 = (t) => (e, o) => {
	void 0 !== o ? o.addInitializer(() => {
		customElements.define(t, e);
	}) : customElements.define(t, e);
};
// node_modules/@lit/reactive-element/decorators/property.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var o$3 = {
	attribute: !0,
	type: String,
	converter: u$4,
	reflect: !1,
	hasChanged: f$2
};
var r$3 = (t = o$3, e, r) => {
	const { kind: n, metadata: i } = r;
	let s = globalThis.litPropertyMetadata.get(i);
	if (void 0 === s && globalThis.litPropertyMetadata.set(i, s = /* @__PURE__ */ new Map()), "setter" === n && ((t = Object.create(t)).wrapped = !0), s.set(r.name, t), "accessor" === n) {
		const { name: o } = r;
		return {
			set(r) {
				const n = e.get.call(this);
				e.set.call(this, r), this.requestUpdate(o, n, t, !0, r);
			},
			init(e) {
				return void 0 !== e && this.C(o, void 0, t, e), e;
			}
		};
	}
	if ("setter" === n) {
		const { name: o } = r;
		return function(r) {
			const n = this[o];
			e.call(this, r), this.requestUpdate(o, n, t, !0, r);
		};
	}
	throw Error("Unsupported decorator location: " + n);
};
function n$2(t) {
	return (e, o) => "object" == typeof o ? r$3(t, e, o) : ((t, e, o) => {
		const r = e.hasOwnProperty(o);
		return e.constructor.createProperty(o, t), r ? Object.getOwnPropertyDescriptor(e, o) : void 0;
	})(t, e, o);
}
// node_modules/@lit/reactive-element/decorators/state.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ function r$2(r) {
	return n$2({
		...r,
		state: !0,
		attribute: !1
	});
}
// node_modules/@lit/reactive-element/decorators/base.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var e$6 = (e, t, c) => (c.configurable = !0, c.enumerable = !0, Reflect.decorate && "object" != typeof t && Object.defineProperty(e, t, c), c);
// node_modules/@lit/reactive-element/decorators/query.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ function e$5(e, r) {
	return (n, s, i) => {
		const o = (t) => t.renderRoot?.querySelector(e) ?? null;
		if (r) {
			const { get: e, set: r } = "object" == typeof s ? n : i ?? (() => {
				const t = Symbol();
				return {
					get() {
						return this[t];
					},
					set(e) {
						this[t] = e;
					}
				};
			})();
			return e$6(n, s, { get() {
				let t = e.call(this);
				return void 0 === t && (t = o(this), (null !== t || this.hasUpdated) && r.call(this, t)), t;
			} });
		}
		return e$6(n, s, { get() {
			return o(this);
		} });
	};
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.AOKMSJXD.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var host_styles_default = i$7`
  :host {
    box-sizing: border-box;
  }

  :host *,
  :host *::before,
  :host *::after {
    box-sizing: inherit;
  }

  [hidden],
  :host([hidden]) {
    display: none !important;
  }
`;
var HAS_ENDING_COLON = /;\s+$/;
function camelToKebab(str) {
	return str.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
}
function buildStyleAttribute(options) {
	const { property: property2, value, element } = options;
	if (value) {
		let style = element.getAttribute("style") || "";
		if (style) {
			if (!style.match(HAS_ENDING_COLON)) style += ";";
			style += " ";
		}
		const str = `${property2}: ${value}`;
		if (style.includes(str)) return;
		return `${style}${str};`;
	}
	return null;
}
var _hasRecordedInitialProperties;
var WebAwesomeElement = class extends i$4 {
	constructor() {
		super();
		__privateAdd(this, _hasRecordedInitialProperties, false);
		this.initialReflectedProperties = /* @__PURE__ */ new Map();
		this.didSSR = Boolean(this.shadowRoot);
		/**
		* @internal Methods for setting and checking custom states.
		*/
		this.customStates = {
			/** Adds or removes the specified custom state. */
			set: (customState, active) => {
				if (!Boolean(this.internals?.states)) return;
				try {
					if (active) this.internals.states.add(customState);
					else this.internals.states.delete(customState);
				} catch (e) {
					if (String(e).includes("must start with '--'")) console.error("Your browser implements an outdated version of CustomStateSet. Consider using a polyfill");
					else throw e;
				}
			},
			/** Determines whether or not the element currently has the specified state. */
			has: (customState) => {
				if (!Boolean(this.internals?.states)) return false;
				try {
					return this.internals.states.has(customState);
				} catch {
					return false;
				}
			}
		};
		try {
			this.internals = this.attachInternals();
		} catch {
			console.error("Element internals are not supported in your browser. Consider using a polyfill");
		}
		this.customStates.set("wa-defined", true);
		let Self = this.constructor;
		for (let [property2, spec] of Self.elementProperties) if (spec.default === "inherit" && spec.initial !== void 0 && typeof property2 === "string") this.customStates.set(`initial-${property2}-${spec.initial}`, true);
	}
	/** Prepends host styles to the component's styles. */
	static get styles() {
		return [host_styles_default, ...Array.isArray(this.css) ? this.css : this.css ? [this.css] : []];
	}
	connectedCallback() {
		super.connectedCallback();
		if (!this.didSSR) this.shadowRoot?.prepend(document.createComment(` Web Awesome: https://webawesome.com/docs/components/${this.localName.replace("wa-", "")} `));
		if (this.didSSR) this.updateComplete.then(() => {
			this.shadowRoot?.prepend(document.createComment(` Web Awesome: https://webawesome.com/docs/components/${this.localName.replace("wa-", "")} `));
		});
	}
	attributeChangedCallback(name, oldValue, newValue) {
		if (!__privateGet(this, _hasRecordedInitialProperties)) {
			this.constructor.elementProperties.forEach((obj, prop) => {
				if (obj.reflect && this[prop] != null) this.initialReflectedProperties.set(prop, this[prop]);
			});
			__privateSet(this, _hasRecordedInitialProperties, true);
		}
		super.attributeChangedCallback(name, oldValue, newValue);
	}
	willUpdate(changedProperties) {
		super.willUpdate(changedProperties);
		this.initialReflectedProperties.forEach((value, prop) => {
			if (changedProperties.has(prop) && this[prop] == null) this[prop] = value;
		});
	}
	firstUpdated(changedProperties) {
		super.firstUpdated(changedProperties);
		if (this.didSSR) this.shadowRoot?.querySelectorAll("slot").forEach((slotElement) => {
			slotElement.dispatchEvent(new Event("slotchange", {
				bubbles: true,
				composed: false,
				cancelable: false
			}));
		});
	}
	update(changedProperties) {
		try {
			super.update(changedProperties);
		} catch (e) {
			if (this.didSSR && !this.hasUpdated) {
				const event = new Event("lit-hydration-error", {
					bubbles: true,
					composed: true,
					cancelable: false
				});
				event.error = e;
				this.dispatchEvent(event);
			}
			throw e;
		}
	}
	/**
	* @internal
	* Internal way to set styles across both client and server
	*/
	setStyle(property2, value) {
		if (!this.style) {
			const str = buildStyleAttribute({
				property: camelToKebab(property2),
				value,
				element: this
			});
			if (str) this.setAttribute("style", str);
			return;
		}
		this.style[property2] = value;
	}
	/**
	* @internal
	* Internal way to set a CSS custom property across both client and server.
	*/
	setStyleProperty(property2, value) {
		if (!this.style) {
			const str = buildStyleAttribute({
				property: property2,
				value,
				element: this
			});
			if (str) this.setAttribute("style", str);
			return;
		}
		this.style.setProperty(property2, value);
	}
	/**
	* @internal Given a native event, this function cancels it and dispatches it again from the host element using the desired
	* event options.
	*/
	relayNativeEvent(event, eventOptions) {
		event.stopImmediatePropagation();
		this.dispatchEvent(new event.constructor(event.type, {
			...event,
			...eventOptions
		}));
	}
};
_hasRecordedInitialProperties = /* @__PURE__ */ new WeakMap();
__decorateClass([n$2()], WebAwesomeElement.prototype, "dir", 2);
__decorateClass([n$2()], WebAwesomeElement.prototype, "lang", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true,
	attribute: "did-ssr"
})], WebAwesomeElement.prototype, "didSSR", 2);
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.EVUNHVNL.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaBadge = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.variant = "brand";
		this.appearance = "accent";
		this.pill = false;
		this.attention = "none";
	}
	render() {
		return b`
      <span part="start">
        <slot name="start"></slot>
      </span>

      <span part="base badge" role="status">
        <slot></slot>
      </span>

      <span part="end">
        <slot name="end"></slot>
      </span>
    `;
	}
};
WaBadge.css = [variants_styles_default, badge_styles_default];
__decorateClass([n$2({ reflect: true })], WaBadge.prototype, "variant", 2);
__decorateClass([n$2({ reflect: true })], WaBadge.prototype, "appearance", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaBadge.prototype, "pill", 2);
__decorateClass([n$2({ reflect: true })], WaBadge.prototype, "attention", 2);
WaBadge = __decorateClass([t$2("wa-badge")], WaBadge);
// node_modules/@awesome.me/webawesome/dist/components/badge/badge.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.R7QX4M6R.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var MirrorValidator = () => {
	return { checkValidity(element) {
		const formControl = element.input;
		const validity = {
			message: "",
			isValid: true,
			invalidKeys: []
		};
		if (!formControl) return validity;
		let isValid = true;
		if ("checkValidity" in formControl) isValid = formControl.checkValidity();
		if (isValid) return validity;
		validity.isValid = false;
		if ("validationMessage" in formControl) validity.message = formControl.validationMessage;
		if (!("validity" in formControl)) {
			validity.invalidKeys.push("customError");
			return validity;
		}
		for (const key in formControl.validity) {
			if (key === "valid") continue;
			const checkedKey = key;
			if (formControl.validity[checkedKey]) validity.invalidKeys.push(checkedKey);
		}
		return validity;
	} };
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.VC3BPUZJ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaInvalidEvent = class extends Event {
	constructor() {
		super("wa-invalid", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.KBXNFZQL.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var CustomErrorValidator = () => {
	return {
		observedAttributes: ["custom-error"],
		checkValidity(element) {
			const validity = {
				message: "",
				isValid: true,
				invalidKeys: []
			};
			if (element.customError) {
				validity.message = element.customError;
				validity.isValid = false;
				validity.invalidKeys = ["customError"];
			}
			return validity;
		}
	};
};
var WebAwesomeFormAssociatedElement = class extends WebAwesomeElement {
	constructor() {
		super();
		this.name = null;
		this.disabled = false;
		this.required = false;
		this.assumeInteractionOn = ["input"];
		this.validators = [];
		this.valueHasChanged = false;
		this.hasInteracted = false;
		this.customError = null;
		this.emittedEvents = [];
		this.emitInvalid = (e) => {
			if (e.target !== this) return;
			this.hasInteracted = true;
			this.dispatchEvent(new WaInvalidEvent());
		};
		this.handleInteraction = (event) => {
			const emittedEvents = this.emittedEvents;
			if (!emittedEvents.includes(event.type)) emittedEvents.push(event.type);
			if (emittedEvents.length === this.assumeInteractionOn?.length) this.hasInteracted = true;
		};
		if ("addEventListener" in this) this.addEventListener("invalid", this.emitInvalid);
	}
	/**
	* Validators are static because they have `observedAttributes`, essentially attributes to "watch"
	* for changes. Whenever these attributes change, we want to be notified and update the validator.
	*/
	static get validators() {
		return [CustomErrorValidator()];
	}
	static get observedAttributes() {
		const parentAttrs = new Set(super.observedAttributes || []);
		for (const validator of this.validators) {
			if (!validator.observedAttributes) continue;
			for (const attr of validator.observedAttributes) parentAttrs.add(attr);
		}
		return [...parentAttrs];
	}
	connectedCallback() {
		super.connectedCallback();
		if (this.didSSR && !this.hasUpdated) this.updateComplete.then(() => {
			this.updateValidity();
		});
		else this.updateValidity();
		this.assumeInteractionOn.forEach((event) => {
			this.addEventListener?.(event, this.handleInteraction);
		});
	}
	firstUpdated(...args) {
		super.firstUpdated(...args);
		this.updateValidity();
	}
	willUpdate(changedProperties) {
		if (changedProperties.has("customError")) {
			if (!this.customError) this.customError = null;
			this.setCustomValidity(this.customError || "");
		}
		if (changedProperties.has("value") || changedProperties.has("disabled") || changedProperties.has("defaultValue")) {
			const value = this.value;
			this.updateFormValue(value);
		}
		if (changedProperties.has("disabled")) {
			this.customStates.set("disabled", this.disabled);
			if (this.hasAttribute("disabled") || !this.matches(":disabled")) this.toggleAttribute("disabled", this.disabled);
		}
		super.willUpdate(changedProperties);
		if (this.didSSR && !this.hasUpdated) this.updateComplete.then(() => this.updateValidity());
		else this.updateValidity();
	}
	/**
	* @internal
	*/
	updateFormValue(value) {
		if (Array.isArray(value)) {
			if (this.name) {
				const formData = new FormData();
				for (const val of value) formData.append(this.name, val);
				this.setValue(formData, formData);
			}
		} else this.setValue(value, value);
	}
	get labels() {
		return this.internals.labels;
	}
	getForm() {
		return this.internals.form;
	}
	/**
	* By default, form controls are associated with the nearest containing `<form>` element. This attribute allows you
	* to place the form control outside of a form and associate it with the form that has this `id`. The form must be in
	* the same document or shadow root for this to work.
	*/
	set form(val) {
		if (val) this.setAttribute("form", val);
		else this.removeAttribute("form");
	}
	get form() {
		return this.internals.form;
	}
	get validity() {
		return this.internals.validity;
	}
	get willValidate() {
		return this.internals.willValidate;
	}
	get validationMessage() {
		return this.internals.validationMessage;
	}
	checkValidity() {
		this.updateValidity();
		return this.internals.checkValidity();
	}
	reportValidity() {
		this.updateValidity();
		this.hasInteracted = true;
		return this.internals.reportValidity();
	}
	/**
	* Override this to change where constraint validation popups are anchored.
	*/
	get validationTarget() {
		return this.input || void 0;
	}
	setValidity(...args) {
		const flags = args[0];
		const message = args[1];
		let anchor = args[2];
		if (!anchor) anchor = this.validationTarget;
		this.internals.setValidity(flags, message, anchor || void 0);
		this.requestUpdate("validity");
		this.setCustomStates();
	}
	setCustomStates() {
		const required = Boolean(this.required);
		const isValid = this.internals.validity.valid;
		const hasInteracted = this.hasInteracted;
		this.customStates.set("required", required);
		this.customStates.set("optional", !required);
		this.customStates.set("invalid", !isValid);
		this.customStates.set("valid", isValid);
		this.customStates.set("user-invalid", !isValid && hasInteracted);
		this.customStates.set("user-valid", isValid && hasInteracted);
	}
	/**
	* Do not use this when creating a "Validator". This is intended for end users of components.
	* We track manually defined custom errors so we don't clear them on accident in our validators.
	*
	*/
	setCustomValidity(message) {
		if (!message) {
			this.customError = null;
			this.setValidity({});
			return;
		}
		this.customError = message;
		this.setValidity({ customError: true }, message, this.validationTarget);
	}
	formResetCallback() {
		this.resetValidity();
		this.hasInteracted = false;
		this.valueHasChanged = false;
		this.emittedEvents = [];
		this.updateValidity();
	}
	formDisabledCallback(isDisabled) {
		this.disabled = isDisabled;
		this.updateValidity();
	}
	/**
	* Called when the browser is trying to restore element’s state to state in which case reason is "restore", or when
	* the browser is trying to fulfill autofill on behalf of user in which case reason is "autocomplete". In the case of
	* "restore", state is a string, File, or FormData object previously set as the second argument to setFormValue.
	*/
	formStateRestoreCallback(state, reason) {
		if (this.didSSR && !this.hasUpdated) this.updateComplete.then(() => {
			this.value = state;
			if (reason === "restore") this.resetValidity();
			this.updateValidity();
		});
		else {
			this.value = state;
			if (reason === "restore") this.resetValidity();
			this.updateValidity();
		}
	}
	setValue(...args) {
		const [value, state] = args;
		this.internals.setFormValue(value, state);
	}
	get allValidators() {
		const staticValidators = this.constructor.validators || [];
		const validators = this.validators || [];
		return [...staticValidators, ...validators];
	}
	/**
	* Reset validity is a way of removing manual custom errors and native validation.
	*/
	resetValidity() {
		this.setCustomValidity("");
		this.setValidity({});
	}
	updateValidity() {
		if (this.disabled || this.hasAttribute("disabled") || !this.willValidate) {
			this.resetValidity();
			return;
		}
		const validators = this.allValidators;
		if (!validators?.length) return;
		const flags = { customError: Boolean(this.customError) };
		const formControl = this.validationTarget || this.input || void 0;
		let finalMessage = "";
		for (const validator of validators) {
			const { isValid, message, invalidKeys } = validator.checkValidity(this);
			if (isValid) continue;
			if (!finalMessage) finalMessage = message;
			if (invalidKeys?.length >= 0) invalidKeys.forEach((str) => flags[str] = true);
		}
		if (!finalMessage) finalMessage = this.validationMessage;
		this.setValidity(flags, finalMessage, formControl);
	}
};
WebAwesomeFormAssociatedElement.formAssociated = true;
__decorateClass([n$2({ reflect: true })], WebAwesomeFormAssociatedElement.prototype, "name", 2);
__decorateClass([n$2({ type: Boolean })], WebAwesomeFormAssociatedElement.prototype, "disabled", 2);
__decorateClass([n$2({
	state: true,
	attribute: false
})], WebAwesomeFormAssociatedElement.prototype, "valueHasChanged", 2);
__decorateClass([n$2({
	state: true,
	attribute: false
})], WebAwesomeFormAssociatedElement.prototype, "hasInteracted", 2);
__decorateClass([n$2({
	attribute: "custom-error",
	reflect: true
})], WebAwesomeFormAssociatedElement.prototype, "customError", 2);
__decorateClass([n$2({
	attribute: false,
	state: true,
	type: Object
})], WebAwesomeFormAssociatedElement.prototype, "validity", 1);
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.RPQJAXXR.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var DEPRECATION_MAP = {
	small: "s",
	medium: "m",
	large: "l"
};
var warned = /* @__PURE__ */ new Set();
function warnDeprecatedSize(tagName, value) {
	if (value in DEPRECATION_MAP && !warned.has(`${tagName}:${value}`)) {
		warned.add(`${tagName}:${value}`);
		console.warn(`[${tagName}] size="${value}" is deprecated. Use size="${DEPRECATION_MAP[value]}" instead. The long-form value will be removed in the next major version.`);
	}
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.RWNXKUCF.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var HasSlotController = class {
	constructor(host, ...slotNames) {
		this.slotNames = [];
		this.handleSlotChange = (event) => {
			const slot = event.target;
			if (this.slotNames.includes("[default]") && !slot.name || slot.name && this.slotNames.includes(slot.name)) this.host.requestUpdate();
		};
		(this.host = host).addController(this);
		this.slotNames = slotNames;
	}
	hasDefaultSlot() {
		if (!this.host.childNodes) return false;
		return [...this.host.childNodes].some((node) => {
			if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== "") return true;
			if (node.nodeType === Node.ELEMENT_NODE) {
				const el = node;
				if (el.tagName.toLowerCase() === "wa-visually-hidden") return false;
				if (!el.hasAttribute("slot")) return true;
			}
			return false;
		});
	}
	hasNamedSlot(name) {
		return this.host.querySelector?.(`:scope > [slot="${name}"]`) !== null;
	}
	/**
	* @param slotName     - Name of the slot to look for
	* @param propertyName - Generally we infer via `withHeader` property on the host, but in cases where its different, you can specify a manual property name.
	*/
	test(slotName, propertyName) {
		if (propertyName && this.host.didSSR && !this.host.hasUpdated) return Boolean(this.host[propertyName]);
		return slotName === "[default]" ? this.hasDefaultSlot() : this.hasNamedSlot(slotName);
	}
	hostConnected() {
		const shadowRoot = this.host.shadowRoot;
		if (shadowRoot && "addEventListener" in shadowRoot) shadowRoot.addEventListener("slotchange", this.handleSlotChange);
	}
	hostDisconnected() {
		const shadowRoot = this.host.shadowRoot;
		if (shadowRoot && "removeEventListener" in shadowRoot) shadowRoot.removeEventListener("slotchange", this.handleSlotChange);
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.G5ZZIGWB.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var size_styles_default = i$7`
  :host([size='xs']) {
    font-size: var(--wa-font-size-xs);
  }

  :host([size='s']),
  :host([size='small']) {
    font-size: var(--wa-font-size-s);
  }

  :host([size='m']),
  :host([size='medium']) {
    font-size: var(--wa-font-size-m);
  }

  :host([size='l']),
  :host([size='large']) {
    font-size: var(--wa-font-size-l);
  }

  :host([size='xl']) {
    font-size: var(--wa-font-size-xl);
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.S35PLDPD.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var button_styles_default = i$7`
  @layer wa-component {
    :host {
      display: inline-block;

      /* Workaround because Chrome doesn't like :host(:has()) below
       * https://issues.chromium.org/issues/40062355
       * Firefox doesn't like this nested rule, so both are needed */
      &:has(wa-badge) {
        position: relative;
      }
    }

    /* Apply relative positioning only when needed to position wa-badge
     * This avoids creating a new stacking context for every button */
    :host(:has(wa-badge)) {
      position: relative;
    }
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    user-select: none;
    -webkit-user-select: none;
    white-space: nowrap;
    vertical-align: middle;
    transition-property: background, border, box-shadow, color, opacity, transform;
    transition-duration: var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    transform-origin: center;
    cursor: pointer;
    padding: 0 var(--wa-form-control-padding-inline);
    font-family: inherit;
    font-size: inherit;
    font-weight: var(--wa-font-weight-action);
    height: var(--wa-form-control-height);
    width: 100%;

    background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));

    border-color: transparent;
    color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
    border-start-start-radius: var(--_button-start-start-radius, var(--wa-form-control-border-radius));
    border-start-end-radius: var(--_button-start-end-radius, var(--wa-form-control-border-radius));
    border-end-start-radius: var(--_button-end-start-radius, var(--wa-form-control-border-radius));
    border-end-end-radius: var(--_button-end-end-radius, var(--wa-form-control-border-radius));
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
  }

  /* Hover and active transforms */
  .button:not(.disabled):not(.loading) {
    @media (hover: hover) {
      &:hover {
        transform: var(--wa-button-transform-hover);
      }
    }
    &:active {
      transform: var(--wa-button-transform-active);
    }

    @media (prefers-reduced-motion: reduce) {
      &:hover,
      &:active {
        transform: none;
      }
    }
  }

  /* Appearance modifiers */
  :host([appearance='plain']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
        background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='outlined']) {
    /* Indentation overrides for grouping outlined */
    margin-inline-start: var(--_button-horizontal-indent-outlined);
    margin-block-start: var(--_button-vertical-indent-outlined);

    .button {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: var(--wa-color-border-loud, var(--wa-color-neutral-border-loud));
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
        background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='filled']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal));
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='filled-outlined']) {
    /* Indentation overrides for grouping outlined */
    margin-inline-start: var(--_button-horizontal-indent-outlined);
    margin-block-start: var(--_button-vertical-indent-outlined);

    .button {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='accent']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
      background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud)),
        var(--wa-color-mix-active)
      );
    }
  }

  /* Focus states */
  .button:focus {
    outline: none;
  }

  .button:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled state */
  :host([disabled]) {
    opacity: 0.5;
    cursor: not-allowed;

    /* When disabled, prevent mouse events from bubbling up from children */
    .button {
      pointer-events: none;
    }
  }

  /* Keep it last so Safari doesn't stop parsing this block */
  .button::-moz-focus-inner {
    border: 0;
  }

  /* Icon buttons */
  .button.is-icon-button {
    outline-offset: 2px;
    width: var(--wa-form-control-height);
    aspect-ratio: 1;
  }

  /* Icon buttons with a caret need to grow to fit both the icon and the caret */
  .button.is-icon-button.caret {
    width: auto;
    aspect-ratio: auto;
    min-width: var(--wa-form-control-height);
  }

  /* Pill modifier */
  :host([pill]) .button {
    border-start-start-radius: var(--_button-start-start-radius, var(--wa-border-radius-pill));
    border-start-end-radius: var(--_button-start-end-radius, var(--wa-border-radius-pill));
    border-end-start-radius: var(--_button-end-start-radius, var(--wa-border-radius-pill));
    border-end-end-radius: var(--_button-end-end-radius, var(--wa-border-radius-pill));
  }

  /*
   * Label
   */

  .start,
  .end {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    pointer-events: none;
  }

  .label {
    display: inline-block;
  }

  .is-icon-button .label {
    display: flex;
    justify-content: center;
  }

  .label::slotted(wa-icon) {
    align-self: center;
  }

  /*
   * Caret modifier
   */

  wa-icon[part='caret'] {
    display: flex;
    align-self: center;
    align-items: center;

    &::part(svg) {
      width: 0.875em;
      height: 0.875em;
    }

    .button:has(&) .end {
      display: none;
    }
  }

  /*
   * Loading modifier
   */

  .loading {
    position: relative;
    cursor: wait;

    .start,
    .label,
    .end,
    .caret {
      /* Hidden with opacity, not visibility, so the label stays in the accessibility tree */
      opacity: 0;

      /* Unlike visibility: hidden, opacity leaves the content clickable */
      pointer-events: none;
    }

    wa-spinner {
      --indicator-color: currentColor;
      --track-color: color-mix(in oklab, currentColor, transparent 90%);

      position: absolute;
      font-size: 1em;
      height: 1em;
      width: 1em;
      top: calc(50% - 0.5em);
      left: calc(50% - 0.5em);
    }
  }

  /*
   * Badges
   */

  .button ::slotted(wa-badge) {
    border-color: var(--wa-color-surface-default);
    position: absolute;
    inset-block-start: 0;
    inset-inline-end: 0;
    translate: 50% -50%;
    pointer-events: none;
  }

  :host(:dir(rtl)) ::slotted(wa-badge) {
    translate: -50% -50%;
  }

  /*
  * Button spacing
  */

  slot[name='start']::slotted(*) {
    margin-inline-end: 0.75em;
  }

  slot[name='end']::slotted(*),
  .button:not(.visually-hidden-label) [part='caret'] {
    margin-inline-start: 0.75em;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.PZAN6FPN.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function watch(propertyName, options) {
	const resolvedOptions = {
		waitUntilFirstUpdate: false,
		...options
	};
	return (proto, decoratedFnName) => {
		const { update } = proto;
		const watchedProperties = Array.isArray(propertyName) ? propertyName : [propertyName];
		proto.update = function(changedProps) {
			watchedProperties.forEach((property) => {
				const key = property;
				if (changedProps.has(key)) {
					const oldValue = changedProps.get(key);
					const newValue = this[key];
					if (oldValue !== newValue) {
						if (!resolvedOptions.waitUntilFirstUpdate || this.hasUpdated) this[decoratedFnName](oldValue, newValue);
					}
				}
			});
			update.call(this, changedProps);
		};
	};
}
// node_modules/@shoelace-style/localize/dist/index.js
var connectedElements = /* @__PURE__ */ new Set();
var translations = /* @__PURE__ */ new Map();
var fallback;
var documentDirection = "ltr";
var documentLanguage = "en";
var isClient = typeof MutationObserver !== "undefined" && typeof document !== "undefined" && typeof document.documentElement !== "undefined";
if (isClient) {
	const documentElementObserver = new MutationObserver(update);
	documentDirection = document.documentElement.dir || "ltr";
	documentLanguage = document.documentElement.lang || navigator.language;
	documentElementObserver.observe(document.documentElement, {
		attributes: true,
		attributeFilter: ["dir", "lang"]
	});
}
function registerTranslation(...translation) {
	translation.map((t) => {
		const code = t.$code.toLowerCase();
		if (translations.has(code)) translations.set(code, Object.assign(Object.assign({}, translations.get(code)), t));
		else translations.set(code, t);
		if (!fallback) fallback = t;
	});
	update();
}
function update() {
	if (isClient) {
		documentDirection = document.documentElement.dir || "ltr";
		documentLanguage = document.documentElement.lang || navigator.language;
	}
	[...connectedElements.keys()].map((el) => {
		if (typeof el.requestUpdate === "function") el.requestUpdate();
	});
}
var LocalizeController$1 = class {
	constructor(host) {
		this.host = host;
		this.host.addController(this);
	}
	hostConnected() {
		connectedElements.add(this.host);
	}
	hostDisconnected() {
		connectedElements.delete(this.host);
	}
	dir() {
		return `${this.host.dir || documentDirection}`.toLowerCase();
	}
	lang() {
		const lang = `${this.host.lang || documentLanguage}`.toLowerCase().replace(/_/g, "-");
		try {
			new Intl.Locale(lang);
			return lang;
		} catch (_a) {
			return fallback ? fallback.$code.toLowerCase() : "en";
		}
	}
	getTranslationData(lang) {
		var _a, _b;
		let locale;
		try {
			locale = new Intl.Locale(lang.replace(/_/g, "-"));
		} catch (_c) {
			return {
				locale: void 0,
				language: "",
				region: "",
				primary: void 0,
				secondary: void 0
			};
		}
		const language = locale.language.toLowerCase();
		const region = (_b = (_a = locale.region) === null || _a === void 0 ? void 0 : _a.toLowerCase()) !== null && _b !== void 0 ? _b : "";
		const primary = translations.get(`${language}-${region}`);
		const secondary = translations.get(language);
		return {
			locale,
			language,
			region,
			primary,
			secondary
		};
	}
	exists(key, options) {
		var _a;
		const { primary, secondary } = this.getTranslationData((_a = options.lang) !== null && _a !== void 0 ? _a : this.lang());
		options = Object.assign({ includeFallback: false }, options);
		if (primary && primary[key] || secondary && secondary[key] || options.includeFallback && fallback && fallback[key]) return true;
		return false;
	}
	term(key, ...args) {
		const { primary, secondary } = this.getTranslationData(this.lang());
		let term;
		if (primary && primary[key]) term = primary[key];
		else if (secondary && secondary[key]) term = secondary[key];
		else if (fallback && fallback[key]) term = fallback[key];
		else {
			console.error(`No translation found for: ${String(key)}`);
			return String(key);
		}
		if (typeof term === "function") return term(...args);
		return term;
	}
	date(dateToFormat, options) {
		dateToFormat = new Date(dateToFormat);
		return new Intl.DateTimeFormat(this.lang(), options).format(dateToFormat);
	}
	number(numberToFormat, options) {
		numberToFormat = Number(numberToFormat);
		return isNaN(numberToFormat) ? "" : new Intl.NumberFormat(this.lang(), options).format(numberToFormat);
	}
	relativeTime(value, unit, options) {
		return new Intl.RelativeTimeFormat(this.lang(), options).format(value, unit);
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.35XIIBFX.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var translation = {
	$code: "en",
	$name: "English",
	$dir: "ltr",
	alignCenter: "Align center",
	alignEnd: "Align end",
	alignJustify: "Justify",
	alignment: "Alignment",
	alignStart: "Align start",
	allTagsRemoved: "All tags removed",
	alternativeText: "Alternative text",
	am: "AM",
	apply: "Apply",
	autosizeColumn: "Autosize column",
	blockquote: "Blockquote",
	bold: "Bold",
	bulletList: "Bulleted list",
	caption: "Caption",
	captions: "Captions",
	carousel: "Carousel",
	cell: "Cell",
	chooseDate: "Choose date",
	chooseDecade: "Choose decade",
	chooseMonth: "Choose month",
	chooseTime: "Choose time",
	chooseYear: "Choose year",
	clearEntry: "Clear entry",
	clearFilter: "Clear filter",
	clearFormatting: "Clear formatting",
	clearSort: "Clear sort",
	close: "Close",
	closeCalendar: "Close calendar",
	closeTimeInput: "Close time picker",
	code: "Code",
	codeBlock: "Code block",
	collapseRow: "Collapse row",
	colorBlue: "Blue",
	colorGray: "Gray",
	colorGreen: "Green",
	colorOrange: "Orange",
	colorPink: "Pink",
	colorPurple: "Purple",
	colorRed: "Red",
	colorYellow: "Yellow",
	column: "Column",
	columnMenu: "Column options",
	columnMovedToPosition: (label, position, total) => `${label} moved to position ${position} of ${total}`,
	columns: "Columns",
	compactPageXOfY: (page, total) => `${page} of ${total}`,
	completed: "Completed",
	copied: "Copied",
	copy: "Copy",
	createOption: (value) => `Create "${value}"`,
	currentlyPlaying: "currently playing",
	currentValue: "Current value",
	date: "Date",
	datePickerKeyboardHelp: "Use arrow keys to change values; press Alt+Down Arrow to open the calendar.",
	day: "Day",
	dayPeriod: "AM/PM",
	decrement: "Decrement",
	deleteColumn: "Delete column",
	deleteRow: "Delete row",
	deleteTable: "Delete table",
	deselectAllRows: "Deselect all rows",
	disabled: "Disabled",
	dropFileHere: "Drop file here or click to browse",
	dropFilesHere: "Drop files here or click to browse",
	editEmbed: "Edit embed",
	editImage: "Edit image",
	editLink: "Edit link",
	embed: "Embed",
	embedPlaceholder: "Paste a URL or embed code",
	embedRemoved: "Embed removed",
	embedUrl: "Embed URL",
	empty: "Empty",
	endDate: "End date",
	enterAtLeastNumCharacters: (min) => `Enter at least ${min} characters`,
	enterFullscreen: "Enter fullscreen",
	enterUpToNumCharacters: (max) => `Enter up to ${max} characters`,
	error: "Error",
	exitFullscreen: "Exit fullscreen",
	expandRow: "Expand row",
	filterByColumn: (label) => `Filter by ${label}`,
	filterFrom: "From",
	filterMax: "Max",
	filterMin: "Min",
	filterTo: "To",
	firstPage: "First page",
	formatMenu: "More formatting",
	formatting: "Formatting",
	goToSlide: (slide, count) => `Go to slide ${slide} of ${count}`,
	heading: "Heading",
	headingLevel: (level) => `Heading ${level}`,
	hideColumn: "Hide column",
	hidePassword: "Hide password",
	highlight: "Highlight",
	highlightColor: "Highlight color",
	horizontalRule: "Horizontal rule",
	hour: "Hour",
	image: "Image",
	imageRemoved: "Image removed",
	imageUrl: "Image URL",
	incompleteDate: "Enter a valid date.",
	increment: "Increment",
	indent: "Indent",
	inlineWithText: "In line with text",
	insertColumnAfter: "Insert column after",
	insertColumnBefore: "Insert column before",
	insertEmbed: "Insert embed",
	insertImage: "Insert image",
	insertLink: "Insert link",
	insertRowAbove: "Insert row above",
	insertRowBelow: "Insert row below",
	insertTable: "Insert table",
	insertTableOfSize: (rows, columns) => `Insert ${rows} by ${columns} table`,
	italic: "Italic",
	jumpBackwardX: (count) => `Jump back ${count} pages`,
	jumpForwardX: (count) => `Jump forward ${count} pages`,
	keyAlt: "Alt",
	keyCtrl: "Ctrl",
	keyShift: "Shift",
	lastPage: "Last page",
	lightbox: "Lightbox",
	link: "Link",
	linkRemoved: "Link removed",
	linkUrl: "Link URL",
	lists: "Lists",
	loading: "Loading",
	locked: "Locked",
	mediaLoadError: "Unable to load media",
	mergeCells: "Merge cells",
	minute: "Minute",
	month: "Month",
	moreOptions: "More Options",
	moveColumnAfter: "Move column after",
	moveColumnBefore: "Move column before",
	moveRowDown: "Move row down",
	moveRowUp: "Move row up",
	mute: "Mute",
	nextDecade: "Next decade",
	nextMonth: "Next month",
	nextPage: "Next page",
	nextSlide: "Next slide",
	nextVideo: "Next Video",
	nextYear: "Next year",
	noColor: "No color",
	noData: "No data",
	noOptions: "No options",
	noResults: "No matching results",
	noSuggestions: "No suggestions",
	notCompleted: "Not completed",
	now: "Now",
	numCharacters: (num) => {
		if (num === 1) return "1 character";
		return `${num} characters`;
	},
	numCharactersRemaining: (num) => {
		if (num === 1) return "1 character remaining";
		return `${num} characters remaining`;
	},
	numOptionsAvailable: (num) => {
		if (num === 0) return "No options available";
		if (num === 1) return "1 option available";
		return `${num} options available`;
	},
	numOptionsSelected: (num) => {
		if (num === 0) return "No options selected";
		if (num === 1) return "1 option selected";
		return `${num} options selected`;
	},
	numRowsCopied: (num) => num === 1 ? "1 row copied" : `${num} rows copied`,
	numRowsSelected: (num) => num === 1 ? "1 row selected" : `${num} rows selected`,
	openInNewTab: "Open in new tab",
	openLink: "Open link",
	optionPosition: (label, position, total) => `${label}, ${position} of ${total}`,
	optionsLoadError: "Options could not be loaded",
	orderedList: "Numbered list",
	outdent: "Outdent",
	pageXOfY: (page, total) => `Page ${page} of ${total}`,
	pagination: "Pagination",
	paragraph: "Paragraph",
	pasteAsPlainText: "Paste as plain text",
	pause: "Pause",
	pauseAnimation: "Pause animation",
	pictureInPicture: "Picture in picture",
	pinLeft: "Pin left",
	pinRight: "Pin right",
	play: "Play",
	playAnimation: "Play animation",
	playbackSpeed: "Playback speed",
	playlist: "Playlist",
	pm: "PM",
	previousDecade: "Previous decade",
	previousMonth: "Previous month",
	previousPage: "Previous page",
	previousSlide: "Previous slide",
	previousVideo: "Previous video",
	previousYear: "Previous year",
	progress: "Progress",
	rangeTooLong: (max) => {
		if (max === 1) return "Select a range no longer than 1 day";
		return `Select a range no longer than ${max} days`;
	},
	rangeTooShort: (min) => {
		if (min === 1) return "Select a range at least 1 day long";
		return `Select a range at least ${min} days long`;
	},
	readonly: "Read-only",
	redo: "Redo",
	remove: "Remove",
	removeLink: "Remove link",
	resetColumns: "Reset columns",
	resize: "Resize",
	resizeColumn: "Resize column",
	row: "Row",
	rowsAndColumns: (rows, columns) => `${rows} rows, ${columns} columns`,
	rowsPerPage: "Rows per page",
	scrollableRegion: "Scrollable region",
	scrollToEnd: "Scroll to end",
	scrollToStart: "Scroll to start",
	search: "Search",
	second: "Second",
	seek: "Seek",
	seekProgress: (current, duration) => `${current} of ${duration}`,
	selectAColorFromTheScreen: "Select a color from the screen",
	selectAllRows: "Select all rows",
	selectCell: "Select cell",
	selected: "Selected",
	selectedDateLabel: (date) => `Selected: ${date}`,
	selectedRangeLabel: (range) => `Selected range: ${range}`,
	selectGroup: "Select group",
	selectionCleared: "Selection cleared",
	selectRow: "Select row",
	selectTable: "Select table",
	showingNofMRows: (shown, total) => `Showing ${shown} of ${total} rows`,
	showingXtoYofZ: (start, end, total) => `${start}\u2013${end} of ${total}`,
	showPassword: "Show password",
	slideNum: (slide) => `Slide ${slide}`,
	sortAscending: "Sort ascending",
	sortColumn: "Sort column",
	sortDescending: "Sort descending",
	splitCell: "Split cell",
	startDate: "Start date",
	steps: "Steps",
	stepXOfY: (step, total) => `Step ${step} of ${total}`,
	strikethrough: "Strikethrough",
	subscript: "Subscript",
	suggestions: "Suggestions",
	suggestionsAvailable: (count) => count === 1 ? "1 suggestion available" : `${count} suggestions available`,
	suggestionsLoadError: "Suggestions could not be loaded",
	superscript: "Superscript",
	tableInserted: "Table inserted",
	tableOptions: "Table options",
	tableSize: "Table size",
	tagAdded: (tag) => `${tag} added`,
	tagAlreadyAdded: (tag) => `${tag} is already added`,
	tagInputKeyboardHelp: "Press Backspace or Delete to remove this tag.",
	tagRemoved: (tag) => `${tag} removed`,
	textColor: "Text color",
	textStyle: "Text style",
	time: "Time",
	timeInputKeyboardHelp: "Use arrow keys to change values; press Alt+Down Arrow to open the time picker.",
	title: "Title",
	today: "Today",
	toggleColorFormat: "Toggle color format",
	toggleHeaderColumn: "Header column",
	toggleHeaderRow: "Header row",
	tooFewTags: (min) => min === 1 ? "Add at least 1 tag" : `Add at least ${min} tags`,
	tooManyTags: (max) => max === 1 ? "Add no more than 1 tag" : `Add no more than ${max} tags`,
	underline: "Underline",
	undo: "Undo",
	unmute: "Unmute",
	unpin: "Unpin",
	unpinColumn: "Unpin column",
	url: "URL",
	videoPlayer: "Video player",
	volume: "Volume",
	wrapTextEnd: "Image at end, text wraps",
	wrapTextStart: "Image at start, text wraps",
	year: "Year",
	zoomIn: "Zoom in",
	zoomOut: "Zoom out"
};
registerTranslation(translation);
var en_default = translation;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.CZIZ2N7K.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var LocalizeController = class extends LocalizeController$1 {
	lang() {
		if (this.host.didSSR && !this.host.hasUpdated) return this.host.lang || "en";
		return super.lang();
	}
};
registerTranslation(en_default);
// node_modules/lit-html/directive.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var t$1 = {
	ATTRIBUTE: 1,
	CHILD: 2,
	PROPERTY: 3,
	BOOLEAN_ATTRIBUTE: 4,
	EVENT: 5,
	ELEMENT: 6
};
var e$4 = (t) => (...e) => ({
	_$litDirective$: t,
	values: e
});
var i$3 = class {
	constructor(t) {}
	get _$AU() {
		return this._$AM._$AU;
	}
	_$AT(t, e, i) {
		this._$Ct = t, this._$AM = e, this._$Ci = i;
	}
	_$AS(t, e) {
		return this.update(t, e);
	}
	update(t, e) {
		return this.render(...e);
	}
};
// node_modules/lit-html/directives/class-map.js
/**
* @license
* Copyright 2018 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var e$3 = e$4(class extends i$3 {
	constructor(t) {
		if (super(t), t.type !== t$1.ATTRIBUTE || "class" !== t.name || t.strings?.length > 2) throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.");
	}
	render(t) {
		return " " + Object.keys(t).filter((s) => t[s]).join(" ") + " ";
	}
	update(s, [i]) {
		if (void 0 === this.st) {
			this.st = /* @__PURE__ */ new Set(), void 0 !== s.strings && (this.nt = new Set(s.strings.join(" ").split(/\s/).filter((t) => "" !== t)));
			for (const t in i) i[t] && !this.nt?.has(t) && this.st.add(t);
			return this.render(i);
		}
		const r = s.element.classList;
		for (const t of this.st) t in i || (r.remove(t), this.st.delete(t));
		for (const t in i) {
			const s = !!i[t];
			s === this.st.has(t) || this.nt?.has(t) || (s ? (r.add(t), this.st.add(t)) : (r.remove(t), this.st.delete(t)));
		}
		return E;
	}
});
// node_modules/lit-html/directives/if-defined.js
/**
* @license
* Copyright 2018 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var o$2 = (o) => o ?? A;
// node_modules/lit-html/static.js
/**
* @license
* Copyright 2020 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var a = Symbol.for("");
var o$1 = (t) => {
	if (t?.r === a) return t?._$litStatic$;
};
var i$2 = (t, ...r) => ({
	_$litStatic$: r.reduce((r, e, a) => r + ((t) => {
		if (void 0 !== t._$litStatic$) return t._$litStatic$;
		throw Error(`Value passed to 'literal' function must be a 'literal' result: ${t}. Use 'unsafeStatic' to pass non-literal values, but\n            take care to ensure page security.`);
	})(e) + t[a + 1], t[0]),
	r: a
});
var l$2 = /* @__PURE__ */ new Map();
var n$1 = (t) => (r, ...e) => {
	const a = e.length;
	let s, i;
	const n = [], u = [];
	let c, $ = 0, f = !1;
	for (; $ < a;) {
		for (c = r[$]; $ < a && void 0 !== (i = e[$], s = o$1(i));) c += s + r[++$], f = !0;
		$ !== a && u.push(i), n.push(c), $++;
	}
	if ($ === a && n.push(r[a]), f) {
		const t = n.join("$$lit$$");
		void 0 === (r = l$2.get(t)) && (n.raw = n, l$2.set(t, r = n)), e = u;
	}
	return t(r, ...e);
};
var u$2 = n$1(b);
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.R2GT5Y4P.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaButton = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super(...arguments);
		this.assumeInteractionOn = ["click"];
		this.hasSlotController = new HasSlotController(this, "[default]", "start", "end");
		this.localize = new LocalizeController(this);
		this.invalid = false;
		this.isIconButton = false;
		this.title = "";
		this.variant = "neutral";
		this.appearance = "accent";
		this.size = "m";
		this.withCaret = false;
		this.withStart = false;
		this.withEnd = false;
		this.disabled = false;
		this.loading = false;
		this.pill = false;
		this.type = "button";
	}
	static get validators() {
		return [...super.validators, MirrorValidator()];
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	constructLightDOMButton() {
		const button = document.createElement("button");
		for (const attribute of this.attributes) {
			if (attribute.name === "style") continue;
			button.setAttribute(attribute.name, attribute.value);
		}
		button.type = this.type;
		button.style.position = "absolute !important";
		button.style.width = "0 !important";
		button.style.height = "0 !important";
		button.style.clipPath = "inset(50%) !important";
		button.style.overflow = "hidden !important";
		button.style.whiteSpace = "nowrap !important";
		if (this.name) button.name = this.name;
		button.value = this.value || "";
		return button;
	}
	handleClick(event) {
		if (this.disabled || this.loading) {
			event.preventDefault();
			event.stopImmediatePropagation();
			return;
		}
		if (this.type !== "submit" && this.type !== "reset") return;
		if (!this.getForm()) return;
		let handled = false;
		const activate = () => {
			if (handled) return;
			handled = true;
			window.removeEventListener("click", onWindowClick);
			if (event.defaultPrevented) return;
			const lightDOMButton = this.constructLightDOMButton();
			this.parentElement?.append(lightDOMButton);
			lightDOMButton.click();
			lightDOMButton.remove();
		};
		const onWindowClick = (e) => {
			if (e === event) activate();
		};
		window.addEventListener("click", onWindowClick);
		setTimeout(activate);
	}
	handleInvalid() {
		this.dispatchEvent(new WaInvalidEvent());
	}
	handleLabelSlotChange() {
		const nodes = this.labelSlot.assignedNodes({ flatten: true });
		let hasIconLabel = false;
		let hasIcon = false;
		let hasText = false;
		let hasOtherElements = false;
		[...nodes].forEach((node) => {
			if (node.nodeType === Node.ELEMENT_NODE) {
				const element = node;
				if (element.localName === "wa-icon") {
					hasIcon = true;
					if (!hasIconLabel) hasIconLabel = element.label !== void 0;
				} else hasOtherElements = true;
			} else if (node.nodeType === Node.TEXT_NODE) {
				if ((node.textContent?.trim() || "").length > 0) hasText = true;
			}
		});
		this.isIconButton = hasIcon && !hasText && !hasOtherElements;
		this.customStates.set("icon-button", this.isIconButton);
		if (this.isIconButton && !hasIconLabel) console.warn("Icon buttons must have a label for screen readers. Add <wa-icon label=\"...\"> to remove this warning.", this);
	}
	isButton() {
		return this.href ? false : true;
	}
	isLink() {
		return this.href ? true : false;
	}
	handleDisabledChange() {
		this.customStates.set("disabled", this.disabled);
		this.updateValidity();
	}
	handleHrefChange() {
		this.customStates.set("link", this.isLink());
	}
	handleLoadingChange() {
		this.customStates.set("loading", this.loading);
	}
	setValue(..._args) {}
	/** Simulates a click on the button. */
	click() {
		this.button.click();
	}
	/** Sets focus on the button. */
	focus(options) {
		this.button.focus(options);
	}
	/** Removes focus from the button. */
	blur() {
		this.button.blur();
	}
	render() {
		const isLink = this.isLink();
		const tag = isLink ? i$2`a` : i$2`button`;
		return u$2`
      <${tag}
        part="base button"
        class=${e$3({
			button: true,
			caret: this.withCaret,
			disabled: this.disabled,
			loading: this.loading,
			rtl: this.localize.dir() === "rtl",
			"has-label": this.hasSlotController.test("[default]"),
			"has-start": this.hasSlotController.test("start", "withStart"),
			"has-end": this.hasSlotController.test("end", "withEnd"),
			"is-icon-button": this.isIconButton
		})}
        ?disabled=${o$2(isLink ? void 0 : this.disabled)}
        type=${o$2(isLink ? void 0 : this.type)}
        title=${this.title}
        name=${o$2(isLink ? void 0 : this.name)}
        value=${o$2(isLink ? void 0 : this.value)}
        href=${o$2(isLink ? this.href : void 0)}
        target=${o$2(isLink ? this.target : void 0)}
        download=${o$2(isLink ? this.download : void 0)}
        rel=${o$2(isLink && this.rel ? this.rel : void 0)}
        role=${o$2(isLink ? void 0 : "button")}
        aria-disabled=${o$2(isLink && this.disabled ? "true" : void 0)}
        aria-busy=${this.loading ? "true" : "false"}
        tabindex=${this.disabled ? "-1" : "0"}
        @invalid=${this.isButton() ? this.handleInvalid : null}
        @click=${this.handleClick}
      >
        <slot name="start" part="start" class="start"></slot>
        <slot part="label" class="label" @slotchange=${this.handleLabelSlotChange}></slot>
        <slot name="end" part="end" class="end"></slot>
        ${this.withCaret ? u$2`
                <wa-icon part="caret" class="caret" library="system" name="chevron-down" variant="solid"></wa-icon>
              ` : ""}
        ${this.loading ? u$2`<wa-spinner part="spinner"></wa-spinner>` : ""}
      </${tag}>
    `;
	}
};
WaButton.shadowRootOptions = {
	...WebAwesomeFormAssociatedElement.shadowRootOptions,
	delegatesFocus: true
};
WaButton.css = [
	button_styles_default,
	variants_styles_default,
	size_styles_default
];
__decorateClass([e$5(".button")], WaButton.prototype, "button", 2);
__decorateClass([e$5("slot:not([name])")], WaButton.prototype, "labelSlot", 2);
__decorateClass([r$2()], WaButton.prototype, "invalid", 2);
__decorateClass([r$2()], WaButton.prototype, "isIconButton", 2);
__decorateClass([n$2()], WaButton.prototype, "title", 2);
__decorateClass([n$2({ reflect: true })], WaButton.prototype, "variant", 2);
__decorateClass([n$2({ reflect: true })], WaButton.prototype, "appearance", 2);
__decorateClass([n$2({ reflect: true })], WaButton.prototype, "size", 2);
__decorateClass([watch("size")], WaButton.prototype, "handleSizeChange", 1);
__decorateClass([n$2({
	attribute: "with-caret",
	type: Boolean,
	reflect: true
})], WaButton.prototype, "withCaret", 2);
__decorateClass([n$2({
	attribute: "with-start",
	type: Boolean
})], WaButton.prototype, "withStart", 2);
__decorateClass([n$2({
	attribute: "with-end",
	type: Boolean
})], WaButton.prototype, "withEnd", 2);
__decorateClass([n$2({ type: Boolean })], WaButton.prototype, "disabled", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaButton.prototype, "loading", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaButton.prototype, "pill", 2);
__decorateClass([n$2()], WaButton.prototype, "type", 2);
__decorateClass([n$2({ reflect: true })], WaButton.prototype, "name", 2);
__decorateClass([n$2({ reflect: true })], WaButton.prototype, "value", 2);
__decorateClass([n$2({ reflect: true })], WaButton.prototype, "href", 2);
__decorateClass([n$2()], WaButton.prototype, "target", 2);
__decorateClass([n$2()], WaButton.prototype, "rel", 2);
__decorateClass([n$2()], WaButton.prototype, "download", 2);
__decorateClass([n$2({ attribute: "formaction" })], WaButton.prototype, "formAction", 2);
__decorateClass([n$2({ attribute: "formenctype" })], WaButton.prototype, "formEnctype", 2);
__decorateClass([n$2({ attribute: "formmethod" })], WaButton.prototype, "formMethod", 2);
__decorateClass([n$2({
	attribute: "formnovalidate",
	type: Boolean
})], WaButton.prototype, "formNoValidate", 2);
__decorateClass([n$2({ attribute: "formtarget" })], WaButton.prototype, "formTarget", 2);
__decorateClass([watch("disabled", { waitUntilFirstUpdate: true })], WaButton.prototype, "handleDisabledChange", 1);
__decorateClass([watch("href")], WaButton.prototype, "handleHrefChange", 1);
__decorateClass([watch("loading", { waitUntilFirstUpdate: true })], WaButton.prototype, "handleLoadingChange", 1);
WaButton = __decorateClass([t$2("wa-button")], WaButton);
WaButton.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.W7A2VLCT.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var spinner_styles_default = i$7`
  :host {
    --track-width: 2px;
    --track-color: var(--wa-color-neutral-fill-normal);
    --indicator-color: var(--wa-color-brand-fill-loud);
    --speed: 2s;
    --size: 1em;

    /*
      Resizing a spinner element using anything but font-size will break the animation because the animation uses em
      units. Therefore, if a spinner is used in a flex container without \`flex: none\` applied, the spinner can
      grow/shrink and break the animation. The use of \`flex: none\` on the host element prevents this by always having
      the spinner sized according to its actual dimensions.
    */
    flex: none;
    display: inline-flex;
    width: var(--size);
    height: var(--size);
  }

  svg {
    width: 100%;
    height: 100%;
    aspect-ratio: 1;
    animation: spin var(--speed) linear infinite;
  }

  .track,
  .indicator {
    --radius: calc(var(--size) / 2 - var(--track-width) / 2);
    --circumference: calc(var(--radius) * 2 * 3.141592654);

    cx: calc(var(--size) / 2);
    cy: calc(var(--size) / 2);
    r: var(--radius);
    fill: none;
    stroke-width: var(--track-width);
  }

  .track {
    stroke: var(--track-color);
  }

  .indicator {
    stroke: var(--indicator-color);
    stroke-linecap: round;
    stroke-dasharray: calc(0.597 * var(--circumference)), calc(0.796 * var(--circumference));
    stroke-dashoffset: calc(-0.04 * var(--circumference));
    animation: dash 1.5s ease-in-out infinite;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes dash {
    0% {
      stroke-dasharray: calc(0.008 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: 0;
    }
    50% {
      stroke-dasharray: calc(0.716 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: calc(-0.278 * var(--circumference));
    }
    100% {
      stroke-dasharray: calc(0.716 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: calc(-0.987 * var(--circumference));
    }
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.AT4ZOBT7.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaSpinner = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
	}
	render() {
		return b`
      <svg
        part="base spinner"
        role="progressbar"
        aria-label=${this.localize.term("loading")}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle class="track" />
        <circle class="indicator" />
      </svg>
    `;
	}
};
WaSpinner.css = spinner_styles_default;
WaSpinner = __decorateClass([t$2("wa-spinner")], WaSpinner);
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.YDQCS2HK.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaErrorEvent = class extends Event {
	constructor() {
		super("wa-error", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.WDIIGUNP.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaLoadEvent = class extends Event {
	constructor() {
		super("wa-load", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.O74G5RVH.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var icon_styles_default = i$7`
  :host {
    --primary-color: currentColor;
    --primary-opacity: 1;
    --secondary-color: currentColor;
    --secondary-opacity: 0.4;
    --rotate-angle: 0deg;

    box-sizing: content-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: -0.125em;
  }

  /* #region Canvas — the box the icon is centered within (mirrors Font Awesome's icon canvas). Orthogonal to font-size. */

  /* Fixed width (default): 1.25em × 1em (20 × 16px) */
  :host(:not([canvas])),
  :host([canvas='fixed']) {
    width: 1.25em;
    height: 1em;
    min-width: 1.25em; /* <-- this is what Safari respects for intrinsic */
    min-height: 1em;
  }

  /* Auto: hug the icon's width. \`auto-width\` is the deprecated alias for canvas="auto". */
  :host([canvas='auto']),
  :host([auto-width]:not([canvas])) {
    width: auto;
    height: 1em;
  }

  /* Square: 1.25em × 1.25em (20 × 20px) */
  :host([canvas='square']) {
    width: 1.25em;
    height: 1.25em;
    min-width: 1.25em;
    min-height: 1.25em;
  }

  /* Roomy: 1.5em × 1.5em (24 × 24px) */
  :host([canvas='roomy']) {
    width: 1.5em;
    height: 1.5em;
    min-width: 1.5em;
    min-height: 1.5em;
  }

  /* #endregion */

  svg {
    /* NOTE: Avoid setting fill here. A stylesheet rule beats SVG presentation attributes, breaking stroke-based
       libraries like Lucide (fill="none" stroke="currentColor") and attribute-based mutators (issue #1733). The default
       library applies fill="currentColor" in its mutator instead. */
    height: 1em;
    overflow: visible;
    width: auto;

    /* Duotone colors with path-specific opacity fallback */
    path[data-duotone-primary] {
      color: var(--primary-color);
      opacity: var(--path-opacity, var(--primary-opacity));
    }

    path[data-duotone-secondary] {
      color: var(--secondary-color);
      opacity: var(--path-opacity, var(--secondary-opacity));
    }
  }

  /* Rotation */
  :host([rotate]) {
    transform: rotate(var(--rotate-angle, 0deg));
  }

  /* Flipping */
  :host([flip='x']) {
    transform: scaleX(-1);
  }
  :host([flip='y']) {
    transform: scaleY(-1);
  }
  :host([flip='both']) {
    transform: scale(-1, -1);
  }

  /* Rotation and Flipping combined */
  :host([rotate][flip='x']) {
    transform: rotate(var(--rotate-angle, 0deg)) scaleX(-1);
  }
  :host([rotate][flip='y']) {
    transform: rotate(var(--rotate-angle, 0deg)) scaleY(-1);
  }
  :host([rotate][flip='both']) {
    transform: rotate(var(--rotate-angle, 0deg)) scale(-1, -1);
  }

  /* #region Animations — ported from Font Awesome 7.3 (--fa-* props mapped to wa-icon's --* names) */

  :host([animation='beat']) {
    animation-name: beat;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='bounce']) {
    animation-name: bounce;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, cubic-bezier(0.28, 0.84, 0.42, 1));
  }

  :host([animation='fade']) {
    animation-name: fade;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='beat-fade']) {
    animation-name: beat-fade;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='flip']) {
    animation-name: flip;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1.5s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='flip-360']) {
    animation-name: flip-360;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='shake']) {
    animation-name: shake;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.75s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='spin']) {
    animation-name: spin;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 2s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-pulse']) {
    animation-name: spin;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, steps(8));
  }

  /* spin-reverse is FA's reverse modifier expressed as a standalone value; reverse any spin via --animation-direction: reverse */
  :host([animation='spin-reverse']) {
    animation-name: spin;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, reverse);
    animation-duration: var(--animation-duration, 2s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-snap']) {
    animation-name: spin-snap;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 3s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-snap-4']) {
    animation-name: spin-snap-4;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 2.4s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-snap-8']) {
    animation-name: spin-snap-8;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 4s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='buzz']) {
    animation-name: buzz;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.6s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='wag']) {
    animation-name: wag;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.9s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-out);
    transform-origin: bottom center;
  }

  :host([animation='float']) {
    animation-name: float;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 3s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
    will-change: transform;
  }

  :host([animation='swing']) {
    animation-name: swing;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1.2s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-out);
    transform-origin: top center;
  }

  :host([animation='jello']) {
    animation-name: jello;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.9s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-out);
  }

  @media (prefers-reduced-motion: reduce) {
    :host([animation='beat']),
    :host([animation='bounce']),
    :host([animation='fade']),
    :host([animation='beat-fade']),
    :host([animation='flip']),
    :host([animation='flip-360']),
    :host([animation='shake']),
    :host([animation='spin']),
    :host([animation='spin-pulse']),
    :host([animation='spin-reverse']),
    :host([animation='spin-snap']),
    :host([animation='spin-snap-4']),
    :host([animation='spin-snap-8']),
    :host([animation='buzz']),
    :host([animation='wag']),
    :host([animation='float']),
    :host([animation='swing']),
    :host([animation='jello']) {
      animation: none !important;
      transition: none !important;
    }
  }

  /* #endregion */

  /* #region Keyframes — ported verbatim from Font Awesome 7.3 */

  @keyframes beat {
    0% {
      transform: scale(1);
    }
    25% {
      transform: scale(calc(1.25 * var(--beat-scale, 1.25)));
    }
    45% {
      transform: scale(calc(1.22 * var(--beat-scale, 1.22)));
    }
    65% {
      transform: scale(calc(1.25 * var(--beat-scale, 1.25)));
    }
    90% {
      transform: scale(1);
    }
  }

  @keyframes bounce {
    0% {
      transform: scale(1, 1) translateY(0);
      /* No fallback by design (ported from FA 7.3): the first segment uses the user's --animation-timing or the CSS
         initial ease, while the explicit cubic-beziers on later stops drive the bounce physics. */
      animation-timing-function: var(--animation-timing);
    }
    14% {
      transform: scale(var(--bounce-start-scale-x, 1.06), var(--bounce-start-scale-y, 0.94))
        translateY(var(--bounce-anticipation, 3px));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    32% {
      transform: scale(var(--bounce-jump-scale-x, 0.94), var(--bounce-jump-scale-y, 1.12))
        translateY(calc(-1 * var(--bounce-height, 0.5em)));
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    52% {
      transform: scale(1, 1) translateY(calc(-1 * var(--bounce-height, 0.5em) * 1.1));
      animation-timing-function: cubic-bezier(0.5, 0, 1, 0.5);
    }
    70% {
      transform: scale(var(--bounce-land-scale-x, 1.06), var(--bounce-land-scale-y, 0.92)) translateY(0);
      animation-timing-function: cubic-bezier(0.33, 0.33, 0.66, 1);
    }
    85% {
      transform: scale(0.98, 1.04) translateY(calc(-2px * var(--bounce-rebound, 1)));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: scale(1, 1) translateY(0);
    }
  }

  @keyframes fade {
    0% {
      opacity: 1;
      transform: scale(1);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    40% {
      opacity: var(--fade-opacity, 0.4);
      transform: scale(0.98);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @keyframes beat-fade {
    0% {
      opacity: var(--beat-fade-opacity, 0.4);
      transform: scale(1);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    25% {
      opacity: calc(var(--beat-fade-opacity, 0.4) + 0.4);
      transform: scale(var(--beat-fade-scale, 1.28));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    45% {
      opacity: 1;
      transform: scale(var(--beat-fade-scale, 1.25));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    65% {
      opacity: calc(var(--beat-fade-opacity, 0.4) + 0.4);
      transform: scale(var(--beat-fade-scale, 1.28));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    100% {
      opacity: var(--beat-fade-opacity, 0.4);
      transform: scale(1);
    }
  }

  @keyframes flip {
    0% {
      transform: perspective(2em) scale(1) rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    8% {
      transform: perspective(2em) scale(var(--flip-anticipation-scale, 0.95))
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    35% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), calc(var(--flip-angle, -360deg) * 0.6));
      animation-timing-function: linear;
    }
    65% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), calc(var(--flip-angle, -360deg) * 0.5));
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    92% {
      transform: perspective(2em) scale(1)
        rotate3d(
          var(--flip-x, 0),
          var(--flip-y, 1),
          var(--flip-z, 0),
          calc(var(--flip-angle, -360deg) * var(--flip-overshoot, 1.04))
        );
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), var(--flip-angle, -360deg));
    }
  }

  @keyframes flip-360 {
    0% {
      transform: perspective(2em) scale(1) rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    8% {
      transform: perspective(2em) scale(var(--flip-anticipation-scale, 0.95))
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    50% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), calc(var(--flip-angle, -360deg) * 0.6));
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    80% {
      transform: perspective(2em) scale(1)
        rotate3d(
          var(--flip-x, 0),
          var(--flip-y, 1),
          var(--flip-z, 0),
          calc(var(--flip-angle, -360deg) * var(--flip-overshoot, 1.04))
        );
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), var(--flip-angle, -360deg));
    }
  }

  @keyframes shake {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
    }
    8% {
      transform: rotate(35deg) translateX(1px);
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    20% {
      transform: rotate(-22deg) translateX(-1px);
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    35% {
      transform: rotate(15deg) translateX(1px);
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    50% {
      transform: rotate(-9deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    65% {
      transform: rotate(5deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    78% {
      transform: rotate(-3deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    90% {
      transform: rotate(1deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    100% {
      transform: rotate(0deg);
    }
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes spin-snap {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    12% {
      transform: rotate(60deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    16.67% {
      transform: rotate(60deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    28.67% {
      transform: rotate(120deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    33.33% {
      transform: rotate(120deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    45.33% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    50% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    62% {
      transform: rotate(240deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    66.67% {
      transform: rotate(240deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    78.67% {
      transform: rotate(300deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    83.33% {
      transform: rotate(300deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    95.33% {
      transform: rotate(360deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes spin-snap-4 {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    15% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    25% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    40% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    50% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    65% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    75% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    90% {
      transform: rotate(360deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes spin-snap-8 {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    9% {
      transform: rotate(45deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    12.5% {
      transform: rotate(45deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    21.5% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    25% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    34% {
      transform: rotate(135deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    37.5% {
      transform: rotate(135deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    46.5% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    50% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    59% {
      transform: rotate(225deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    62.5% {
      transform: rotate(225deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    71.5% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    75% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    84% {
      transform: rotate(315deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    87.5% {
      transform: rotate(315deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    96.5% {
      transform: rotate(360deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes buzz {
    0% {
      transform: translateX(0) rotate(0deg);
      animation-timing-function: cubic-bezier(0.1, 0, 0.9, 1);
    }
    5% {
      transform: translateX(var(--buzz-distance, 4px)) rotate(0.5deg);
    }
    10% {
      transform: translateX(calc(-1 * var(--buzz-distance, 4px))) rotate(-0.5deg);
    }
    15% {
      transform: translateX(var(--buzz-distance, 4px)) rotate(0.3deg);
    }
    20% {
      transform: translateX(calc(-1 * var(--buzz-distance, 4px))) rotate(-0.3deg);
    }
    25% {
      transform: translateX(calc(var(--buzz-distance, 4px) * 0.7)) rotate(0.2deg);
    }
    30% {
      transform: translateX(calc(-1 * var(--buzz-distance, 4px) * 0.7)) rotate(-0.2deg);
    }
    35% {
      transform: translateX(calc(var(--buzz-distance, 4px) * 0.4)) rotate(0.1deg);
    }
    40% {
      transform: translateX(0) rotate(0deg);
    }
    100% {
      transform: translateX(0) rotate(0deg);
    }
  }

  @keyframes wag {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
    }
    12% {
      transform: rotate(var(--wag-angle, 12deg));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    24% {
      transform: rotate(2deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
    }
    36% {
      transform: rotate(calc(var(--wag-angle, 12deg) * 0.85));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    48% {
      transform: rotate(1deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
    }
    58% {
      transform: rotate(calc(var(--wag-angle, 12deg) * 0.6));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    68% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(0deg);
    }
  }

  @keyframes float {
    0% {
      transform: translateY(0) translateX(0) rotate(0deg)
        scale(var(--float-squash-x, 1.02), var(--float-squash-y, 0.98));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    15% {
      transform: translateY(calc(-0.4 * var(--float-height, 6px))) translateX(var(--float-drift, 1px))
        rotate(var(--float-tilt, 1deg)) scale(1, 1);
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    35% {
      transform: translateY(calc(-1 * var(--float-height, 6px))) translateX(0) rotate(0deg)
        scale(var(--float-stretch-x, 0.98), var(--float-stretch-y, 1.03));
      animation-timing-function: cubic-bezier(0.5, 0, 0.5, 0);
    }
    50% {
      transform: translateY(calc(-0.92 * var(--float-height, 6px))) translateX(calc(-0.5 * var(--float-drift, 1px)))
        rotate(calc(-0.5 * var(--float-tilt, 1deg))) scale(0.995, 1.01);
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    70% {
      transform: translateY(calc(-0.3 * var(--float-height, 6px))) translateX(calc(-1 * var(--float-drift, 1px)))
        rotate(calc(-1 * var(--float-tilt, 1deg))) scale(1, 1);
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    90% {
      transform: translateY(calc(0.05 * var(--float-height, 6px))) translateX(0) rotate(0deg)
        scale(var(--float-squash-x, 1.02), var(--float-squash-y, 0.98));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: translateY(0) translateX(0) rotate(0deg)
        scale(var(--float-squash-x, 1.02), var(--float-squash-y, 0.98));
    }
  }

  @keyframes swing {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
    }
    8% {
      transform: rotate(var(--swing-angle, 22deg));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    18% {
      transform: rotate(calc(-1 * var(--swing-angle, 22deg) * 0.85));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    28% {
      transform: rotate(calc(var(--swing-angle, 22deg) * 0.65));
      animation-timing-function: cubic-bezier(0.35, 0, 0.65, 1);
    }
    38% {
      transform: rotate(calc(-1 * var(--swing-angle, 22deg) * 0.45));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    48% {
      transform: rotate(calc(var(--swing-angle, 22deg) * 0.25));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    56% {
      transform: rotate(calc(-1 * var(--swing-angle, 22deg) * 0.1));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    64% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(0deg);
    }
  }

  @keyframes jello {
    0% {
      transform: scale(1, 1);
      animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
    }
    12% {
      transform: scale(var(--jello-scale-x, 1.15), calc(2 - var(--jello-scale-x, 1.15)));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    24% {
      transform: scale(calc(2 - var(--jello-scale-y, 1.12)), var(--jello-scale-y, 1.12));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    36% {
      transform: scale(
        calc(1 + (var(--jello-scale-x, 1.15) - 1) * 0.5),
        calc(2 - (1 + (var(--jello-scale-x, 1.15) - 1) * 0.5))
      );
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    48% {
      transform: scale(
        calc(2 - (1 + (var(--jello-scale-y, 1.12) - 1) * 0.3)),
        calc(1 + (var(--jello-scale-y, 1.12) - 1) * 0.3)
      );
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    58% {
      transform: scale(1.02, 0.98);
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    68% {
      transform: scale(1, 1);
    }
    100% {
      transform: scale(1, 1);
    }
  }

  /* #endregion */
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.PM4OOGCP.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var defaultIconFamily = "";
var defaultIconVariant = "";
function getDefaultIconFamily() {
	if (!defaultIconFamily) defaultIconFamily = document.querySelector("[data-fa-family]")?.getAttribute("data-fa-family") || "classic";
	return defaultIconFamily;
}
function getDefaultIconVariant() {
	if (!defaultIconVariant) defaultIconVariant = document.querySelector("[data-fa-variant]")?.getAttribute("data-fa-variant") || "solid";
	return defaultIconVariant;
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.HGBRCPUS.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var iconPath = "";
var kitCode = "";
function getIconPath() {
	return iconPath.replace(/\/$/, "");
}
function setKitCode(code) {
	kitCode = code;
}
function getKitCode() {
	if (!kitCode) {
		const el = document.querySelector("[data-fa-kit-code]");
		if (el) setKitCode(el.getAttribute("data-fa-kit-code") || "");
	}
	return kitCode;
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.JE7SQLHI.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var FA_VERSION = "7.3.0";
function getIconFolder(_name, family, variant) {
	let folder = "solid";
	if (family === "chisel") folder = "chisel-regular";
	if (family === "etch") folder = "etch-solid";
	if (family === "graphite") folder = "graphite-thin";
	if (family === "jelly") {
		folder = "jelly-regular";
		if (variant === "duo-regular") folder = "jelly-duo-regular";
		if (variant === "fill-regular") folder = "jelly-fill-regular";
	}
	if (family === "jelly-duo") folder = "jelly-duo-regular";
	if (family === "jelly-fill") folder = "jelly-fill-regular";
	if (family === "notdog") {
		if (variant === "solid") folder = "notdog-solid";
		if (variant === "duo-solid") folder = "notdog-duo-solid";
	}
	if (family === "notdog-duo") folder = "notdog-duo-solid";
	if (family === "slab") {
		if (variant === "solid" || variant === "regular") folder = "slab-regular";
		if (variant === "press-regular") folder = "slab-press-regular";
	}
	if (family === "slab-press") folder = "slab-press-regular";
	if (family === "slab-duo") folder = "slab-duo-regular";
	if (family === "slab-press-duo") folder = "slab-press-duo-regular";
	if (family === "thumbprint") folder = "thumbprint-light";
	if (family === "utility") folder = "utility-semibold";
	if (family === "utility-duo") folder = "utility-duo-semibold";
	if (family === "utility-fill") folder = "utility-fill-semibold";
	if (family === "whiteboard") folder = "whiteboard-semibold";
	if (family === "mosaic") folder = "mosaic-solid";
	if (family === "pixel") folder = "pixel-regular";
	if (family === "vellum") folder = "vellum-solid";
	if (family === "classic") {
		if (variant === "thin") folder = "thin";
		if (variant === "light") folder = "light";
		if (variant === "regular") folder = "regular";
		if (variant === "solid") folder = "solid";
	}
	if (family === "duotone") {
		if (variant === "thin") folder = "duotone-thin";
		if (variant === "light") folder = "duotone-light";
		if (variant === "regular") folder = "duotone-regular";
		if (variant === "solid") folder = "duotone";
	}
	if (family === "sharp") {
		if (variant === "thin") folder = "sharp-thin";
		if (variant === "light") folder = "sharp-light";
		if (variant === "regular") folder = "sharp-regular";
		if (variant === "solid") folder = "sharp-solid";
	}
	if (family === "sharp-duotone") {
		if (variant === "thin") folder = "sharp-duotone-thin";
		if (variant === "light") folder = "sharp-duotone-light";
		if (variant === "regular") folder = "sharp-duotone-regular";
		if (variant === "solid") folder = "sharp-duotone-solid";
	}
	if (family === "brands") folder = "brands";
	return folder;
}
function getIconUrl(name, family, variant) {
	const folder = getIconFolder(name, family, variant);
	const iconBase = getIconPath();
	if (iconBase) return `${iconBase}/${folder}/${name}.svg`;
	const kitCode = getKitCode();
	return kitCode.length > 0 ? `https://ka-p.fontawesome.com/releases/v${FA_VERSION}/svgs/${folder}/${name}.svg?token=${encodeURIComponent(kitCode)}` : `https://ka-f.fontawesome.com/releases/v${FA_VERSION}/svgs/${folder}/${name}.svg`;
}
var library_default_default = {
	name: "default",
	resolver: (name, family, variant) => {
		return getIconUrl(name, family || getDefaultIconFamily(), variant || getDefaultIconVariant());
	},
	mutator: (svg, hostEl) => {
		if (!svg.hasAttribute("fill")) svg.setAttribute("fill", "currentColor");
		if (hostEl && !svg.hasAttribute("data-duotone-initialized")) {
			const family = hostEl.family || getDefaultIconFamily();
			const { variant } = hostEl;
			if (family === "duotone" || family === "sharp-duotone" || family === "notdog-duo" || family === "notdog" && variant === "duo-solid" || family === "jelly-duo" || family === "jelly" && variant === "duo-regular" || family === "utility-duo" || family === "slab-duo" || family === "slab-press-duo" || family === "thumbprint") {
				const paths = [...svg.querySelectorAll("path")];
				const primaryPath = paths.find((p) => !p.hasAttribute("opacity"));
				const secondaryPath = paths.find((p) => p.hasAttribute("opacity"));
				if (!primaryPath || !secondaryPath) return;
				primaryPath.setAttribute("data-duotone-primary", "");
				secondaryPath.setAttribute("data-duotone-secondary", "");
				if (hostEl.swapOpacity && primaryPath && secondaryPath) {
					const originalOpacity = secondaryPath.getAttribute("opacity") || "0.4";
					primaryPath.style.setProperty("--path-opacity", originalOpacity);
					secondaryPath.style.setProperty("--path-opacity", "1");
				}
				svg.setAttribute("data-duotone-initialized", "");
			}
		}
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.NRKYOGEO.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var systemIconSets = {};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.L5A4HNJK.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function dataUri(svg) {
	return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
var icons = {
	solid: {
		"align-center": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M352 64c0-17.7-14.3-32-32-32L128 32c-17.7 0-32 14.3-32 32s14.3 32 32 32l192 0c17.7 0 32-14.3 32-32zm96 128c0-17.7-14.3-32-32-32L32 160c-17.7 0-32 14.3-32 32s14.3 32 32 32l384 0c17.7 0 32-14.3 32-32zM0 448c0 17.7 14.3 32 32 32l384 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L32 416c-17.7 0-32 14.3-32 32zM352 320c0-17.7-14.3-32-32-32l-192 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l192 0c17.7 0 32-14.3 32-32z"/></svg>`,
		"align-justify": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M448 64c0-17.7-14.3-32-32-32L32 32C14.3 32 0 46.3 0 64S14.3 96 32 96l384 0c17.7 0 32-14.3 32-32zm0 256c0-17.7-14.3-32-32-32L32 288c-17.7 0-32 14.3-32 32s14.3 32 32 32l384 0c17.7 0 32-14.3 32-32zM0 192c0 17.7 14.3 32 32 32l384 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L32 160c-17.7 0-32 14.3-32 32zM448 448c0-17.7-14.3-32-32-32L32 416c-17.7 0-32 14.3-32 32s14.3 32 32 32l384 0c17.7 0 32-14.3 32-32z"/></svg>`,
		"align-left": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M288 64c0 17.7-14.3 32-32 32L32 96C14.3 96 0 81.7 0 64S14.3 32 32 32l224 0c17.7 0 32 14.3 32 32zm0 256c0 17.7-14.3 32-32 32L32 352c-17.7 0-32-14.3-32-32s14.3-32 32-32l224 0c17.7 0 32 14.3 32 32zM0 192c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 224c-17.7 0-32-14.3-32-32zM448 448c0 17.7-14.3 32-32 32L32 480c-17.7 0-32-14.3-32-32s14.3-32 32-32l384 0c17.7 0 32 14.3 32 32z"/></svg>`,
		"align-right": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M448 64c0 17.7-14.3 32-32 32L192 96c-17.7 0-32-14.3-32-32s14.3-32 32-32l224 0c17.7 0 32 14.3 32 32zm0 256c0 17.7-14.3 32-32 32l-224 0c-17.7 0-32-14.3-32-32s14.3-32 32-32l224 0c17.7 0 32 14.3 32 32zM0 192c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 224c-17.7 0-32-14.3-32-32zM448 448c0 17.7-14.3 32-32 32L32 480c-17.7 0-32-14.3-32-32s14.3-32 32-32l384 0c17.7 0 32 14.3 32 32z"/></svg>`,
		"arrow-down": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M169.4 502.6c12.5 12.5 32.8 12.5 45.3 0l160-160c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 402.7 224 32c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 370.7-105.4-105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160z"/></svg>`,
		"arrow-up": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M214.6 9.4c-12.5-12.5-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 109.3 160 480c0 17.7 14.3 32 32 32s32-14.3 32-32l0-370.7 105.4 105.4c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-160-160z"/></svg>`,
		"arrow-up-right-from-square": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M320 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l82.7 0-201.4 201.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L448 109.3 448 192c0 17.7 14.3 32 32 32s32-14.3 32-32l0-160c0-17.7-14.3-32-32-32L320 0zM80 96C35.8 96 0 131.8 0 176L0 432c0 44.2 35.8 80 80 80l256 0c44.2 0 80-35.8 80-80l0-80c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 80c0 8.8-7.2 16-16 16L80 448c-8.8 0-16-7.2-16-16l0-256c0-8.8 7.2-16 16-16l80 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L80 96z"/></svg>`,
		backward: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M236.3 107.1C247.9 96 265 92.9 279.7 99.2C294.4 105.5 304 120 304 136L304 272.3L476.3 107.2C487.9 96 505 92.9 519.7 99.2C534.4 105.5 544 120 544 136L544 504C544 520 534.4 534.5 519.7 540.8C505 547.1 487.9 544 476.3 532.9L304 367.7L304 504C304 520 294.4 534.5 279.7 540.8C265 547.1 247.9 544 236.3 532.9L44.3 348.9C36.5 341.3 32 330.9 32 320C32 309.1 36.5 298.7 44.3 291.1L236.3 107.1z"/></svg>`,
		"backward-step": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M491 100.8C478.1 93.8 462.3 94.5 450 102.6L192 272.1L192 128C192 110.3 177.7 96 160 96C142.3 96 128 110.3 128 128L128 512C128 529.7 142.3 544 160 544C177.7 544 192 529.7 192 512L192 367.9L450 537.5C462.3 545.6 478 546.3 491 539.3C504 532.3 512 518.8 512 504.1L512 136.1C512 121.4 503.9 107.9 491 100.9z"/></svg>`,
		bars: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2026 Fonticons, Inc. --><path d="M0 96C0 78.3 14.3 64 32 64l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 128C14.3 128 0 113.7 0 96zM0 256c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 288c-17.7 0-32-14.3-32-32zM448 416c0 17.7-14.3 32-32 32L32 448c-17.7 0-32-14.3-32-32s14.3-32 32-32l384 0c17.7 0 32 14.3 32 32z"/></svg>`,
		"angles-left": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M77.3 256 214.7 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256zm192 0L406.7 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L269.3 256z"/></svg>`,
		"angles-right": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M434.7 256 297.3 118.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l160 160c12.5 12.5 12.5 32.8 0 45.3l-160 160c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L434.7 256zm-192 0L105.3 118.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l160 160c12.5 12.5 12.5 32.8 0 45.3l-160 160c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L242.7 256z"/></svg>`,
		bold: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M32 32C14.3 32 0 46.3 0 64S14.3 96 32 96l32 0 0 320-32 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l224 0c70.7 0 128-57.3 128-128 0-46.5-24.8-87.3-62-109.7 18.7-22.3 30-51 30-82.3 0-70.7-57.3-128-128-128L32 32zM288 160c0 35.3-28.7 64-64 64l-96 0 0-128 96 0c35.3 0 64 28.7 64 64zM128 416l0-128 128 0c35.3 0 64 28.7 64 64s-28.7 64-64 64l-128 0z"/></svg>`,
		check: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M434.8 70.1c14.3 10.4 17.5 30.4 7.1 44.7l-256 352c-5.5 7.6-14 12.3-23.4 13.1s-18.5-2.7-25.1-9.3l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l101.5 101.5 234-321.7c10.4-14.3 30.4-17.5 44.7-7.1z"/></svg>`,
		"chevron-down": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M201.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 338.7 54.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z"/></svg>`,
		"chevron-left": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M9.4 233.4c-12.5 12.5-12.5 32.8 0 45.3l192 192c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256 246.6 86.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-192 192z"/></svg>`,
		"chevron-right": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M311.1 233.4c12.5 12.5 12.5 32.8 0 45.3l-192 192c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L243.2 256 73.9 86.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l192 192z"/></svg>`,
		circle: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0z"/></svg>`,
		"closed-captioning": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M64 192C64 156.7 92.7 128 128 128L512 128C547.3 128 576 156.7 576 192L576 448C576 483.3 547.3 512 512 512L128 512C92.7 512 64 483.3 64 448L64 192zM216 272L248 272C252.4 272 256 275.6 256 280C256 293.3 266.7 304 280 304C293.3 304 304 293.3 304 280C304 249.1 278.9 224 248 224L216 224C185.1 224 160 249.1 160 280L160 360C160 390.9 185.1 416 216 416L248 416C278.9 416 304 390.9 304 360C304 346.7 293.3 336 280 336C266.7 336 256 346.7 256 360C256 364.4 252.4 368 248 368L216 368C211.6 368 208 364.4 208 360L208 280C208 275.6 211.6 272 216 272zM384 280C384 275.6 387.6 272 392 272L424 272C428.4 272 432 275.6 432 280C432 293.3 442.7 304 456 304C469.3 304 480 293.3 480 280C480 249.1 454.9 224 424 224L392 224C361.1 224 336 249.1 336 280L336 360C336 390.9 361.1 416 392 416L424 416C454.9 416 480 390.9 480 360C480 346.7 469.3 336 456 336C442.7 336 432 346.7 432 360C432 364.4 428.4 368 424 368L392 368C387.6 368 384 364.4 384 360L384 280z"/></svg>`,
		"closed-captioning-slash": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M39 39.1C48.4 29.7 63.6 29.7 72.9 39.1L161.8 128L512 128C547.3 128 576 156.7 576 192L576 448C576 473.5 561.1 495.4 539.6 505.8L601 567.1C610.4 576.5 610.4 591.7 601 601C591.6 610.3 576.4 610.4 567.1 601L39 73.1C29.7 63.7 29.7 48.5 39 39.1zM384 350.1L384 279.9C384 275.5 387.6 271.9 392 271.9L424 271.9C428.4 271.9 432 275.5 432 279.9C432 293.2 442.7 303.9 456 303.9C469.3 303.9 480 293.2 480 279.9C480 249 454.9 223.9 424 223.9L392 223.9C361.1 223.9 336 249 336 279.9L336 302.1L384 350.1zM445.5 411.6C465.7 403.2 480 383.2 480 359.9C480 346.6 469.3 335.9 456 335.9C442.7 335.9 432 346.6 432 359.9C432 364.3 428.4 367.9 424 367.9L401.8 367.9L445.5 411.6zM162.3 264.1C160.8 269.1 160 274.5 160 280L160 360C160 390.9 185.1 416 216 416L248 416C266.1 416 282.1 407.5 292.4 394.2L410.2 512L128 512C92.7 512 64 483.3 64 448L64 192C64 184.2 65.4 176.7 68 169.8L162.3 264.1zM256.1 357.9C256 358.6 256 359.3 256 360C256 364.4 252.4 368 248 368L216 368C211.6 368 208 364.4 208 360L208 309.8L256.1 357.9z"/></svg>`,
		code: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M360.8 1.2c-17-4.9-34.7 5-39.6 22l-128 448c-4.9 17 5 34.7 22 39.6s34.7-5 39.6-22l128-448c4.9-17-5-34.7-22-39.6zm64.6 136.1c-12.5 12.5-12.5 32.8 0 45.3l73.4 73.4-73.4 73.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0l96-96c12.5-12.5 12.5-32.8 0-45.3l-96-96c-12.5-12.5-32.8-12.5-45.3 0zm-274.7 0c-12.5-12.5-32.8-12.5-45.3 0l-96 96c-12.5 12.5-12.5 32.8 0 45.3l96 96c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256 150.6 182.6c12.5-12.5 12.5-32.8 0-45.3z"/></svg>`,
		compress: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M160 64c0-17.7-14.3-32-32-32S96 46.3 96 64l0 64-64 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l96 0c17.7 0 32-14.3 32-32l0-96zM32 320c-17.7 0-32 14.3-32 32s14.3 32 32 32l64 0 0 64c0 17.7 14.3 32 32 32s32-14.3 32-32l0-96c0-17.7-14.3-32-32-32l-96 0zM352 64c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 96c0 17.7 14.3 32 32 32l96 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-64 0 0-64zM320 320c-17.7 0-32 14.3-32 32l0 96c0 17.7 14.3 32 32 32s32-14.3 32-32l0-64 64 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-96 0z"/></svg>`,
		ellipsis: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.3.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 320C96 289.1 121.1 264 152 264C182.9 264 208 289.1 208 320C208 350.9 182.9 376 152 376C121.1 376 96 350.9 96 320zM264 320C264 289.1 289.1 264 320 264C350.9 264 376 289.1 376 320C376 350.9 350.9 376 320 376C289.1 376 264 350.9 264 320zM488 264C518.9 264 544 289.1 544 320C544 350.9 518.9 376 488 376C457.1 376 432 350.9 432 320C432 289.1 457.1 264 488 264z"/></svg>`,
		"ellipsis-vertical": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M320 208C289.1 208 264 182.9 264 152C264 121.1 289.1 96 320 96C350.9 96 376 121.1 376 152C376 182.9 350.9 208 320 208zM320 432C350.9 432 376 457.1 376 488C376 518.9 350.9 544 320 544C289.1 544 264 518.9 264 488C264 457.1 289.1 432 320 432zM376 320C376 350.9 350.9 376 320 376C289.1 376 264 350.9 264 320C264 289.1 289.1 264 320 264C350.9 264 376 289.1 376 320z"/></svg>`,
		eraser: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M178.5 416l123 0 65.3-65.3-173.5-173.5-126.7 126.7 112 112zM224 480l-45.5 0c-17 0-33.3-6.7-45.3-18.7L17 345C6.1 334.1 0 319.4 0 304s6.1-30.1 17-41L263 17C273.9 6.1 288.6 0 304 0s30.1 6.1 41 17L527 199c10.9 10.9 17 25.6 17 41s-6.1 30.1-17 41l-135 135 120 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-288 0z"/></svg>`,
		expand: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 96C110.3 96 96 110.3 96 128L96 224C96 241.7 110.3 256 128 256C145.7 256 160 241.7 160 224L160 160L224 160C241.7 160 256 145.7 256 128C256 110.3 241.7 96 224 96L128 96zM160 416C160 398.3 145.7 384 128 384C110.3 384 96 398.3 96 416L96 512C96 529.7 110.3 544 128 544L224 544C241.7 544 256 529.7 256 512C256 494.3 241.7 480 224 480L160 480L160 416zM416 96C398.3 96 384 110.3 384 128C384 145.7 398.3 160 416 160L480 160L480 224C480 241.7 494.3 256 512 256C529.7 256 544 241.7 544 224L544 128C544 110.3 529.7 96 512 96L416 96zM544 416C544 398.3 529.7 384 512 384C494.3 384 480 398.3 480 416L480 480L416 480C398.3 480 384 494.3 384 512C384 529.7 398.3 544 416 544L512 544C529.7 544 544 529.7 544 512L544 416z"/></svg>`,
		eyedropper: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M341.6 29.2l-101.6 101.6-9.4-9.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-9.4-9.4 101.6-101.6c39-39 39-102.2 0-141.1s-102.2-39-141.1 0zM55.4 323.3c-15 15-23.4 35.4-23.4 56.6l0 42.4-26.6 39.9c-8.5 12.7-6.8 29.6 4 40.4s27.7 12.5 40.4 4l39.9-26.6 42.4 0c21.2 0 41.6-8.4 56.6-23.4l109.4-109.4-45.3-45.3-109.4 109.4c-3 3-7.1 4.7-11.3 4.7l-36.1 0 0-36.1c0-4.2 1.7-8.3 4.7-11.3l109.4-109.4-45.3-45.3-109.4 109.4z"/></svg>`,
		"fill-drip": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M309.7 71.6l-64.4 64.4 33.4 33.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0l-33.4-33.4-96.4 96.4c-2.9 2.9-5.1 6.5-6.3 10.3l321.5 0 53.7-53.7c4.9-4.9 7.6-11.5 7.6-18.3s-2.7-13.5-7.6-18.3L346.3 71.6C341.5 66.7 334.9 64 328 64s-13.5 2.7-18.3 7.6zM58.3 232.4l96.4-96.4-49.4-49.4c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0L200 90.7 264.4 26.3C281.3 9.5 304.1 0 328 0s46.7 9.5 63.6 26.3L517.7 152.4C534.5 169.3 544 192.1 544 216s-9.5 46.7-26.3 63.6L311.6 485.7C294.7 502.5 271.9 512 248 512s-46.7-9.5-63.6-26.3L58.3 359.6C41.5 342.7 32 319.9 32 296s9.5-46.7 26.3-63.6zM512 544c-35.3 0-64-28.7-64-64 0-25.2 32.6-79.6 51.2-108.7 6-9.4 19.5-9.4 25.5 0 18.7 29.1 51.2 83.5 51.2 108.7 0 35.3-28.7 64-64 64z"/></svg>`,
		film: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 96C0 60.7 28.7 32 64 32l320 0c35.3 0 64 28.7 64 64l0 320c0 35.3-28.7 64-64 64L64 480c-35.3 0-64-28.7-64-64L0 96zM48 368l0 32c0 8.8 7.2 16 16 16l32 0c8.8 0 16-7.2 16-16l0-32c0-8.8-7.2-16-16-16l-32 0c-8.8 0-16 7.2-16 16zm304-16c-8.8 0-16 7.2-16 16l0 32c0 8.8 7.2 16 16 16l32 0c8.8 0 16-7.2 16-16l0-32c0-8.8-7.2-16-16-16l-32 0zM48 240l0 32c0 8.8 7.2 16 16 16l32 0c8.8 0 16-7.2 16-16l0-32c0-8.8-7.2-16-16-16l-32 0c-8.8 0-16 7.2-16 16zm304-16c-8.8 0-16 7.2-16 16l0 32c0 8.8 7.2 16 16 16l32 0c8.8 0 16-7.2 16-16l0-32c0-8.8-7.2-16-16-16l-32 0zM48 112l0 32c0 8.8 7.2 16 16 16l32 0c8.8 0 16-7.2 16-16l0-32c0-8.8-7.2-16-16-16L64 96c-8.8 0-16 7.2-16 16zM352 96c-8.8 0-16 7.2-16 16l0 32c0 8.8 7.2 16 16 16l32 0c8.8 0 16-7.2 16-16l0-32c0-8.8-7.2-16-16-16l-32 0z"/></svg>`,
		filter: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M32 64C19.1 64 7.4 71.8 2.4 83.8S.2 109.5 9.4 118.6L192 301.3 192 416c0 8.5 3.4 16.6 9.4 22.6l64 64c9.2 9.2 22.9 11.9 34.9 6.9S320 492.9 320 480l0-178.7 182.6-182.6c9.2-9.2 11.9-22.9 6.9-34.9S492.9 64 480 64L32 64z"/></svg>`,
		font: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M285.1 50.7C279.9 39.3 268.5 32 256 32s-23.9 7.3-29.1 18.7L59.5 416 48 416c-17.7 0-32 14.3-32 32s14.3 32 32 32l88 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-6.1 0 22-48 208.3 0 22 48-6.1 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l88 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-11.5 0-167.4-365.3zM330.8 304L181.2 304 256 140.8 330.8 304z"/></svg>`,
		forward: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M403.7 107.1C392.1 96 375 92.9 360.3 99.2C345.6 105.5 336 120 336 136L336 272.3L163.7 107.2C152.1 96 135 92.9 120.3 99.2C105.6 105.5 96 120 96 136L96 504C96 520 105.6 534.5 120.3 540.8C135 547.1 152.1 544 163.7 532.9L336 367.7L336 504C336 520 345.6 534.5 360.3 540.8C375 547.1 392.1 544 403.7 532.9L595.7 348.9C603.6 341.4 608 330.9 608 320C608 309.1 603.5 298.7 595.7 291.1L403.7 107.1z"/></svg>`,
		file: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M192 64C156.7 64 128 92.7 128 128L128 512C128 547.3 156.7 576 192 576L448 576C483.3 576 512 547.3 512 512L512 234.5C512 217.5 505.3 201.2 493.3 189.2L386.7 82.7C374.7 70.7 358.5 64 341.5 64L192 64zM453.5 240L360 240C346.7 240 336 229.3 336 216L336 122.5L453.5 240z"/></svg>`,
		"file-audio": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM389.8 307.7C380.7 301.4 368.3 303.6 362 312.7C355.7 321.8 357.9 334.2 367 340.5C390.9 357.2 406.4 384.8 406.4 416C406.4 447.2 390.8 474.9 367 491.5C357.9 497.8 355.7 510.3 362 519.3C368.3 528.3 380.8 530.6 389.8 524.3C423.9 500.5 446.4 460.8 446.4 416C446.4 371.2 424 331.5 389.8 307.7zM208 376C199.2 376 192 383.2 192 392L192 440C192 448.8 199.2 456 208 456L232 456L259.2 490C262.2 493.8 266.8 496 271.7 496L272 496C280.8 496 288 488.8 288 480L288 352C288 343.2 280.8 336 272 336L271.7 336C266.8 336 262.2 338.2 259.2 342L232 376L208 376zM336 448.2C336 458.9 346.5 466.4 354.9 459.8C367.8 449.5 376 433.7 376 416C376 398.3 367.8 382.5 354.9 372.2C346.5 365.5 336 373.1 336 383.8L336 448.3z"/></svg>`,
		"file-code": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM282.2 359.6C290.8 349.5 289.7 334.4 279.6 325.8C269.5 317.2 254.4 318.3 245.8 328.4L197.8 384.4C190.1 393.4 190.1 406.6 197.8 415.6L245.8 471.6C254.4 481.7 269.6 482.8 279.6 474.2C289.6 465.6 290.8 450.4 282.2 440.4L247.6 400L282.2 359.6zM394.2 328.4C385.6 318.3 370.4 317.2 360.4 325.8C350.4 334.4 349.2 349.6 357.8 359.6L392.4 400L357.8 440.4C349.2 450.5 350.3 465.6 360.4 474.2C370.5 482.8 385.6 481.7 394.2 471.6L442.2 415.6C449.9 406.6 449.9 393.4 442.2 384.4L394.2 328.4z"/></svg>`,
		"file-excel": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM292 330.7C284.6 319.7 269.7 316.7 258.7 324C247.7 331.3 244.7 346.3 252 357.3L291.2 416L252 474.7C244.6 485.7 247.6 500.6 258.7 508C269.8 515.4 284.6 512.4 292 501.3L320 459.3L348 501.3C355.4 512.3 370.3 515.3 381.3 508C392.3 500.7 395.3 485.7 388 474.7L348.8 416L388 357.3C395.4 346.3 392.4 331.4 381.3 324C370.2 316.6 355.4 319.6 348 330.7L320 372.7L292 330.7z"/></svg>`,
		"file-image": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM256 320C256 302.3 241.7 288 224 288C206.3 288 192 302.3 192 320C192 337.7 206.3 352 224 352C241.7 352 256 337.7 256 320zM220.6 512L419.4 512C435.2 512 448 499.2 448 483.4C448 476.1 445.2 469 440.1 463.7L343.3 361.9C337.3 355.6 328.9 352 320.1 352L319.8 352C311 352 302.7 355.6 296.6 361.9L199.9 463.7C194.8 469 192 476.1 192 483.4C192 499.2 204.8 512 220.6 512z"/></svg>`,
		"file-pdf": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 64C92.7 64 64 92.7 64 128L64 512C64 547.3 92.7 576 128 576L208 576L208 464C208 428.7 236.7 400 272 400L448 400L448 234.5C448 217.5 441.3 201.2 429.3 189.2L322.7 82.7C310.7 70.7 294.5 64 277.5 64L128 64zM389.5 240L296 240C282.7 240 272 229.3 272 216L272 122.5L389.5 240zM272 444C261 444 252 453 252 464L252 592C252 603 261 612 272 612C283 612 292 603 292 592L292 564L304 564C337.1 564 364 537.1 364 504C364 470.9 337.1 444 304 444L272 444zM304 524L292 524L292 484L304 484C315 484 324 493 324 504C324 515 315 524 304 524zM400 444C389 444 380 453 380 464L380 592C380 603 389 612 400 612L432 612C460.7 612 484 588.7 484 560L484 496C484 467.3 460.7 444 432 444L400 444zM420 572L420 484L432 484C438.6 484 444 489.4 444 496L444 560C444 566.6 438.6 572 432 572L420 572zM508 464L508 592C508 603 517 612 528 612C539 612 548 603 548 592L548 548L576 548C587 548 596 539 596 528C596 517 587 508 576 508L548 508L548 484L576 484C587 484 596 475 596 464C596 453 587 444 576 444L528 444C517 444 508 453 508 464z"/></svg>`,
		"file-powerpoint": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM280 320C266.7 320 256 330.7 256 344L256 488C256 501.3 266.7 512 280 512C293.3 512 304 501.3 304 488L304 464L328 464C367.8 464 400 431.8 400 392C400 352.2 367.8 320 328 320L280 320zM328 416L304 416L304 368L328 368C341.3 368 352 378.7 352 392C352 405.3 341.3 416 328 416z"/></svg>`,
		"file-video": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM208 368L208 464C208 481.7 222.3 496 240 496L336 496C353.7 496 368 481.7 368 464L368 440L403 475C406.2 478.2 410.5 480 415 480C424.4 480 432 472.4 432 463L432 368.9C432 359.5 424.4 351.9 415 351.9C410.5 351.9 406.2 353.7 403 356.9L368 391.9L368 367.9C368 350.2 353.7 335.9 336 335.9L240 335.9C222.3 335.9 208 350.2 208 367.9z"/></svg>`,
		"file-word": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM263.4 338.8C260.5 325.9 247.7 317.7 234.8 320.6C221.9 323.5 213.7 336.3 216.6 349.2L248.6 493.2C250.9 503.7 260 511.4 270.8 512C281.6 512.6 291.4 505.9 294.8 495.6L320 419.9L345.2 495.6C348.6 505.8 358.4 512.5 369.2 512C380 511.5 389.1 503.8 391.4 493.2L423.4 349.2C426.3 336.3 418.1 323.4 405.2 320.6C392.3 317.8 379.4 325.9 376.6 338.8L363.4 398.2L342.8 336.4C339.5 326.6 330.4 320 320 320C309.6 320 300.5 326.6 297.2 336.4L276.6 398.2L263.4 338.8z"/></svg>`,
		"file-zipper": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM192 136C192 149.3 202.7 160 216 160L264 160C277.3 160 288 149.3 288 136C288 122.7 277.3 112 264 112L216 112C202.7 112 192 122.7 192 136zM192 232C192 245.3 202.7 256 216 256L264 256C277.3 256 288 245.3 288 232C288 218.7 277.3 208 264 208L216 208C202.7 208 192 218.7 192 232zM256 304L224 304C206.3 304 192 318.3 192 336L192 384C192 410.5 213.5 432 240 432C266.5 432 288 410.5 288 384L288 336C288 318.3 273.7 304 256 304zM240 368C248.8 368 256 375.2 256 384C256 392.8 248.8 400 240 400C231.2 400 224 392.8 224 384C224 375.2 231.2 368 240 368z"/></svg>`,
		"forward-step": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M21 36.8c12.9-7 28.7-6.3 41 1.8L320 208.1 320 64c0-17.7 14.3-32 32-32s32 14.3 32 32l0 384c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-144.1-258 169.6c-12.3 8.1-28 8.8-41 1.8S0 454.7 0 440L0 72C0 57.3 8.1 43.8 21 36.8z"/></svg>`,
		gauge: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0zm320 96c0-26.9-16.5-49.9-40-59.3L280 120c0-13.3-10.7-24-24-24s-24 10.7-24 24l0 172.7c-23.5 9.5-40 32.5-40 59.3 0 35.3 28.7 64 64 64s64-28.7 64-64zM144 176a32 32 0 1 0 0-64 32 32 0 1 0 0 64zm-16 80a32 32 0 1 0 -64 0 32 32 0 1 0 64 0zm288 32a32 32 0 1 0 0-64 32 32 0 1 0 0 64zM400 144a32 32 0 1 0 -64 0 32 32 0 1 0 64 0z"/></svg>`,
		gear: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M259.1 73.5C262.1 58.7 275.2 48 290.4 48L350.2 48C365.4 48 378.5 58.7 381.5 73.5L396 143.5C410.1 149.5 423.3 157.2 435.3 166.3L503.1 143.8C517.5 139 533.3 145 540.9 158.2L570.8 210C578.4 223.2 575.7 239.8 564.3 249.9L511 297.3C511.9 304.7 512.3 312.3 512.3 320C512.3 327.7 511.8 335.3 511 342.7L564.4 390.2C575.8 400.3 578.4 417 570.9 430.1L541 481.9C533.4 495 517.6 501.1 503.2 496.3L435.4 473.8C423.3 482.9 410.1 490.5 396.1 496.6L381.7 566.5C378.6 581.4 365.5 592 350.4 592L290.6 592C275.4 592 262.3 581.3 259.3 566.5L244.9 496.6C230.8 490.6 217.7 482.9 205.6 473.8L137.5 496.3C123.1 501.1 107.3 495.1 99.7 481.9L69.8 430.1C62.2 416.9 64.9 400.3 76.3 390.2L129.7 342.7C128.8 335.3 128.4 327.7 128.4 320C128.4 312.3 128.9 304.7 129.7 297.3L76.3 249.8C64.9 239.7 62.3 223 69.8 209.9L99.7 158.1C107.3 144.9 123.1 138.9 137.5 143.7L205.3 166.2C217.4 157.1 230.6 149.5 244.6 143.4L259.1 73.5zM320.3 400C364.5 399.8 400.2 363.9 400 319.7C399.8 275.5 363.9 239.8 319.7 240C275.5 240.2 239.8 276.1 240 320.3C240.2 364.5 276.1 400.2 320.3 400z"/></svg>`,
		"grip-lines": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M32 288c-17.7 0-32 14.3-32 32s14.3 32 32 32l384 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L32 288zm0-128c-17.7 0-32 14.3-32 32s14.3 32 32 32l384 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L32 160z"/></svg>`,
		"grip-vertical": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M128 40c0-22.1-17.9-40-40-40L40 0C17.9 0 0 17.9 0 40L0 88c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zm0 192c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zM0 424l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40zM320 40c0-22.1-17.9-40-40-40L232 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zM192 232l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40zM320 424c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48z"/></svg>`,
		heading: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 64C0 46.3 14.3 32 32 32l96 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-16 0 0 112 224 0 0-112-16 0c-17.7 0-32-14.3-32-32s14.3-32 32-32l96 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-16 0 0 320 16 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-96 0c-17.7 0-32-14.3-32-32s14.3-32 32-32l16 0 0-144-224 0 0 144 16 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-96 0c-17.7 0-32-14.3-32-32s14.3-32 32-32l16 0 0-320-16 0C14.3 96 0 81.7 0 64z"/></svg>`,
		highlighter: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M315 315L473.4 99.9 444.1 70.6 229 229 315 315zm-187 5l0 0 0-71.7c0-15.3 7.2-29.6 19.5-38.6L420.6 8.4C428 2.9 437 0 446.2 0 457.6 0 468.5 4.5 476.6 12.6l54.8 54.8c8.1 8.1 12.6 19 12.6 30.5 0 9.2-2.9 18.2-8.4 25.6L334.4 396.5c-9 12.3-23.4 19.5-38.6 19.5l-71.7 0-25.4 25.4c-12.5 12.5-32.8 12.5-45.3 0l-50.7-50.7c-12.5-12.5-12.5-32.8 0-45.3L128 320zM7 466.3l51.7-51.7 70.6 70.6-19.7 19.7c-4.5 4.5-10.6 7-17 7L24 512c-13.3 0-24-10.7-24-24l0-4.7c0-6.4 2.5-12.5 7-17z"/></svg>`,
		image: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M64 32C28.7 32 0 60.7 0 96L0 416c0 35.3 28.7 64 64 64l320 0c35.3 0 64-28.7 64-64l0-320c0-35.3-28.7-64-64-64L64 32zm64 80a48 48 0 1 1 0 96 48 48 0 1 1 0-96zM272 224c8.4 0 16.1 4.4 20.5 11.5l88 144c4.5 7.4 4.7 16.7 .5 24.3S368.7 416 360 416L88 416c-8.9 0-17.2-5-21.3-12.9s-3.5-17.5 1.6-24.8l56-80c4.5-6.4 11.8-10.2 19.7-10.2s15.2 3.8 19.7 10.2l26.4 37.8 61.4-100.5c4.4-7.1 12.1-11.5 20.5-11.5z"/></svg>`,
		indent: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 64C0 46.3 14.3 32 32 32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 96C14.3 96 0 81.7 0 64zM192 192c0-17.7 14.3-32 32-32l192 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-192 0c-17.7 0-32-14.3-32-32zm32 96l192 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-192 0c-17.7 0-32-14.3-32-32s14.3-32 32-32zM0 448c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 480c-17.7 0-32-14.3-32-32zM127.8 268.6L25.8 347.9C15.3 356.1 0 348.6 0 335.3L0 176.7c0-13.3 15.3-20.8 25.8-12.6l101.9 79.3c8.2 6.4 8.2 18.9 0 25.3z"/></svg>`,
		indeterminate: `<svg part="indeterminate-icon" class="icon" viewBox="0 0 16 16"><g stroke="none" stroke-width="1" fill="none" fill-rule="evenodd" stroke-linecap="round"><g stroke="currentColor" stroke-width="2"><g transform="translate(2.285714 6.857143)"><path d="M10.2857143,1.14285714 L1.14285714,1.14285714"/></g></g></g></svg>`,
		italic: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 64c0-17.7 14.3-32 32-32l192 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-58.7 0-133.3 320 64 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 480c-17.7 0-32-14.3-32-32s14.3-32 32-32l58.7 0 133.3-320-64 0c-17.7 0-32-14.3-32-32z"/></svg>`,
		link: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M419.5 96c-16.6 0-32.7 4.5-46.8 12.7-15.8-16-34.2-29.4-54.5-39.5 28.2-24 64.1-37.2 101.3-37.2 86.4 0 156.5 70 156.5 156.5 0 41.5-16.5 81.3-45.8 110.6l-71.1 71.1c-29.3 29.3-69.1 45.8-110.6 45.8-86.4 0-156.5-70-156.5-156.5 0-1.5 0-3 .1-4.5 .5-17.7 15.2-31.6 32.9-31.1s31.6 15.2 31.1 32.9c0 .9 0 1.8 0 2.6 0 51.1 41.4 92.5 92.5 92.5 24.5 0 48-9.7 65.4-27.1l71.1-71.1c17.3-17.3 27.1-40.9 27.1-65.4 0-51.1-41.4-92.5-92.5-92.5zM275.2 173.3c-1.9-.8-3.8-1.9-5.5-3.1-12.6-6.5-27-10.2-42.1-10.2-24.5 0-48 9.7-65.4 27.1L91.1 258.2c-17.3 17.3-27.1 40.9-27.1 65.4 0 51.1 41.4 92.5 92.5 92.5 16.5 0 32.6-4.4 46.7-12.6 15.8 16 34.2 29.4 54.6 39.5-28.2 23.9-64 37.2-101.3 37.2-86.4 0-156.5-70-156.5-156.5 0-41.5 16.5-81.3 45.8-110.6l71.1-71.1c29.3-29.3 69.1-45.8 110.6-45.8 86.6 0 156.5 70.6 156.5 156.9 0 1.3 0 2.6 0 3.9-.4 17.7-15.1 31.6-32.8 31.2s-31.6-15.1-31.2-32.8c0-.8 0-1.5 0-2.3 0-33.7-18-63.3-44.8-79.6z"/></svg>`,
		"link-slash": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M41-24.9c-9.4-9.4-24.6-9.4-33.9 0S-2.3-.3 7 9.1l528 528c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-122-122c4.2-3.4 8.3-7.1 12.1-10.9l71.1-71.1c29.3-29.3 45.8-69.1 45.8-110.6 0-86.4-70-156.5-156.5-156.5-37.3 0-73.1 13.3-101.3 37.2 20.3 10.1 38.7 23.5 54.5 39.5 14.1-8.3 30.2-12.7 46.8-12.7 51.1 0 92.5 41.4 92.5 92.5 0 24.5-9.7 48-27.1 65.4l-71.1 71.1c-3.9 3.9-8.1 7.4-12.6 10.5l-47.5-47.5c16.5-.9 29.7-14.4 30.2-31.1 0-1.3 0-2.6 0-3.9 0-86.3-69.9-156.9-156.5-156.9-19.2 0-37.9 3.5-55.5 10.2L41-24.9zM225.9 160c.6 0 1.1 0 1.7 0 15.1 0 29.5 3.7 42.1 10.2 1.8 1.2 3.6 2.3 5.5 3.1 26.8 16.3 44.8 45.9 44.8 79.6 0 .4 0 .8 0 1.2L225.9 160zM346.2 416L192 261.8c1.2 84.6 69.6 152.9 154.1 154.1zM139.7 209.5l-45.3-45.3-48.6 48.6c-29.3 29.3-45.8 69.1-45.8 110.6 0 86.4 70 156.5 156.5 156.5 37.2 0 73.1-13.3 101.3-37.2-20.3-10.1-38.8-23.5-54.6-39.5-14 8.2-30.1 12.6-46.7 12.6-51.1 0-92.5-41.4-92.5-92.5 0-24.5 9.7-48 27.1-65.4l48.6-48.6z"/></svg>`,
		"list-ol": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 72C0 58.8 10.7 48 24 48l48 0c13.3 0 24 10.7 24 24l0 104 24 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-96 0c-13.3 0-24-10.7-24-24s10.7-24 24-24l24 0 0-80-24 0C10.7 96 0 85.3 0 72zM30.4 301.2C41.8 292.6 55.7 288 70 288l4.9 0c33.7 0 61.1 27.4 61.1 61.1 0 19.6-9.4 37.9-25.2 49.4l-24 17.5 33.2 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-90.7 0C13.1 464 0 450.9 0 434.7 0 425.3 4.5 416.5 12.1 411l70.5-51.3c3.4-2.5 5.4-6.4 5.4-10.6 0-7.2-5.9-13.1-13.1-13.1L70 336c-3.9 0-7.7 1.3-10.8 3.6L38.4 355.2c-10.6 8-25.6 5.8-33.6-4.8S-1 324.8 9.6 316.8l20.8-15.6zM224 64l256 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-256 0c-17.7 0-32-14.3-32-32s14.3-32 32-32zm0 160l256 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-256 0c-17.7 0-32-14.3-32-32s14.3-32 32-32zm0 160l256 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-256 0c-17.7 0-32-14.3-32-32s14.3-32 32-32z"/></svg>`,
		"list-ul": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 144a48 48 0 1 0 0-96 48 48 0 1 0 0 96zM192 64c-17.7 0-32 14.3-32 32s14.3 32 32 32l288 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L192 64zm0 160c-17.7 0-32 14.3-32 32s14.3 32 32 32l288 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-288 0zm0 160c-17.7 0-32 14.3-32 32s14.3 32 32 32l288 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-288 0zM48 464a48 48 0 1 0 0-96 48 48 0 1 0 0 96zM96 256a48 48 0 1 0 -96 0 48 48 0 1 0 96 0z"/></svg>`,
		"magnifying-glass": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z"/></svg>`,
		"magnifying-glass-minus": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2026 Fonticons, Inc. --><path d="M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM136 184c-13.3 0-24 10.7-24 24s10.7 24 24 24l144 0c13.3 0 24-10.7 24-24s-10.7-24-24-24l-144 0z"/></svg>`,
		"magnifying-glass-plus": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2026 Fonticons, Inc. --><path d="M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM208 112c-13.3 0-24 10.7-24 24l0 48-48 0c-13.3 0-24 10.7-24 24s10.7 24 24 24l48 0 0 48c0 13.3 10.7 24 24 24s24-10.7 24-24l0-48 48 0c13.3 0 24-10.7 24-24s-10.7-24-24-24l-48 0 0-48c0-13.3-10.7-24-24-24z"/></svg>`,
		minus: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M0 256c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 288c-17.7 0-32-14.3-32-32z"/></svg>`,
		outdent: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M.4 64c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-384 0C14.8 96 .4 81.7 .4 64zm192 128c0-17.7 14.3-32 32-32l192 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-192 0c-17.7 0-32-14.3-32-32zm32 96l192 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-192 0c-17.7 0-32-14.3-32-32s14.3-32 32-32zM.4 448c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-384 0c-17.7 0-32-14.3-32-32zM.7 268.6c-8.2-6.4-8.2-18.9 0-25.3l101.9-79.3c10.5-8.2 25.8-.7 25.8 12.6l0 158.6c0 13.3-15.3 20.8-25.8 12.6L.7 268.6z"/></svg>`,
		palette: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M512 256c0 .9 0 1.8 0 2.7-.4 36.5-33.6 61.3-70.1 61.3L344 320c-26.5 0-48 21.5-48 48 0 3.4 .4 6.7 1 9.9 2.1 10.2 6.5 20 10.8 29.9 6.1 13.8 12.1 27.5 12.1 42 0 31.8-21.6 60.7-53.4 62-3.5 .1-7 .2-10.6 .2-141.4 0-256-114.6-256-256S114.6 0 256 0 512 114.6 512 256zM128 288a32 32 0 1 0 -64 0 32 32 0 1 0 64 0zm0-96a32 32 0 1 0 0-64 32 32 0 1 0 0 64zM288 96a32 32 0 1 0 -64 0 32 32 0 1 0 64 0zm96 96a32 32 0 1 0 0-64 32 32 0 1 0 0 64z"/></svg>`,
		paragraph: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M160 0L416 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-32 0 0 416c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-416-48 0 0 416c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-160-48 0C71.6 320 0 248.4 0 160S71.6 0 160 0z"/></svg>`,
		paste: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M64 0C28.7 0 0 28.7 0 64L0 384c0 35.3 28.7 64 64 64l112 0 0-224c0-61.9 50.1-112 112-112l64 0 0-48c0-35.3-28.7-64-64-64L64 0zM248 112l-144 0c-13.3 0-24-10.7-24-24s10.7-24 24-24l144 0c13.3 0 24 10.7 24 24s-10.7 24-24 24zm40 48c-35.3 0-64 28.7-64 64l0 224c0 35.3 28.7 64 64 64l160 0c35.3 0 64-28.7 64-64l0-165.5c0-17-6.7-33.3-18.7-45.3l-58.5-58.5c-12-12-28.3-18.7-45.3-18.7L288 160z"/></svg>`,
		pause: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M48 32C21.5 32 0 53.5 0 80L0 432c0 26.5 21.5 48 48 48l64 0c26.5 0 48-21.5 48-48l0-352c0-26.5-21.5-48-48-48L48 32zm224 0c-26.5 0-48 21.5-48 48l0 352c0 26.5 21.5 48 48 48l64 0c26.5 0 48-21.5 48-48l0-352c0-26.5-21.5-48-48-48l-64 0z"/></svg>`,
		"picture-in-picture": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M448 32c35.3 0 64 28.7 64 64l0 112-64 0 0-112-384 0 0 320 144 0 0 64-144 0-6.5-.3c-30.1-3.1-54.1-27-57.1-57.1L0 416 0 96C0 62.9 25.2 35.6 57.5 32.3L64 32 448 32zm16 224c26.5 0 48 21.5 48 48l0 128c0 26.5-21.5 48-48 48l-160 0c-26.5 0-48-21.5-48-48l0-128c0-26.5 21.5-48 48-48l160 0z"/></svg>`,
		play: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M91.2 36.9c-12.4-6.8-27.4-6.5-39.6 .7S32 57.9 32 72l0 368c0 14.1 7.5 27.2 19.6 34.4s27.2 7.5 39.6 .7l336-184c12.8-7 20.8-20.5 20.8-35.1s-8-28.1-20.8-35.1l-336-184z"/></svg>`,
		"play-circle": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0zM188.3 147.1c-7.6 4.2-12.3 12.3-12.3 20.9l0 176c0 8.7 4.7 16.7 12.3 20.9s16.8 4.1 24.3-.5l144-88c7.1-4.4 11.5-12.1 11.5-20.5s-4.4-16.1-11.5-20.5l-144-88c-7.4-4.5-16.7-4.7-24.3-.5z"/></svg>`,
		plus: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M352 128C352 110.3 337.7 96 320 96C302.3 96 288 110.3 288 128L288 288L128 288C110.3 288 96 302.3 96 320C96 337.7 110.3 352 128 352L288 352L288 512C288 529.7 302.3 544 320 544C337.7 544 352 529.7 352 512L352 352L512 352C529.7 352 544 337.7 544 320C544 302.3 529.7 288 512 288L352 288L352 128z"/></svg>`,
		"quote-left": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 216C0 149.7 53.7 96 120 96l8 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-8 0c-30.9 0-56 25.1-56 56l0 8 64 0c35.3 0 64 28.7 64 64l0 64c0 35.3-28.7 64-64 64l-64 0c-35.3 0-64-28.7-64-64L0 216zm256 0c0-66.3 53.7-120 120-120l8 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-8 0c-30.9 0-56 25.1-56 56l0 8 64 0c35.3 0 64 28.7 64 64l0 64c0 35.3-28.7 64-64 64l-64 0c-35.3 0-64-28.7-64-64l0-136z"/></svg>`,
		"rotate-left": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M24 192l144 0c9.7 0 18.5-5.8 22.2-14.8s1.7-19.3-5.2-26.2l-46.7-46.7c75.3-58.6 184.3-53.3 253.5 15.9 75 75 75 196.5 0 271.5s-196.5 75-271.5 0c-10.2-10.2-19-21.3-26.4-33-9.5-14.9-29.3-19.3-44.2-9.8s-19.3 29.3-9.8 44.2C49.7 408.7 61.4 423.5 75 437 175 537 337 537 437 437S537 175 437 75C342.8-19.3 193.3-24.7 92.7 58.8L41 7C34.1 .2 23.8-1.9 14.8 1.8S0 14.3 0 24L0 168c0 13.3 10.7 24 24 24z"/></svg>`,
		"rotate-right": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M488 192l-144 0c-9.7 0-18.5-5.8-22.2-14.8s-1.7-19.3 5.2-26.2l46.7-46.7c-75.3-58.6-184.3-53.3-253.5 15.9-75 75-75 196.5 0 271.5s196.5 75 271.5 0c8.2-8.2 15.5-16.9 21.9-26.1 10.1-14.5 30.1-18 44.6-7.9s18 30.1 7.9 44.6c-8.5 12.2-18.2 23.8-29.1 34.7-100 100-262.1 100-362 0S-25 175 75 75c94.3-94.3 243.7-99.6 344.3-16.2L471 7c6.9-6.9 17.2-8.9 26.2-5.2S512 14.3 512 24l0 144c0 13.3-10.7 24-24 24z"/></svg>`,
		star: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M309.5-18.9c-4.1-8-12.4-13.1-21.4-13.1s-17.3 5.1-21.4 13.1L193.1 125.3 33.2 150.7c-8.9 1.4-16.3 7.7-19.1 16.3s-.5 18 5.8 24.4l114.4 114.5-25.2 159.9c-1.4 8.9 2.3 17.9 9.6 23.2s16.9 6.1 25 2L288.1 417.6 432.4 491c8 4.1 17.7 3.3 25-2s11-14.2 9.6-23.2L441.7 305.9 556.1 191.4c6.4-6.4 8.6-15.8 5.8-24.4s-10.1-14.9-19.1-16.3L383 125.3 309.5-18.9z"/></svg>`,
		strikethrough: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 157.5C96 88.2 152.2 32 221.5 32L368 32c17.7 0 32 14.3 32 32s-14.3 32-32 32L221.5 96c-34 0-61.5 27.5-61.5 61.5 0 31 23.1 57.2 53.9 61l44.1 5.5 222 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 288c-17.7 0-32-14.3-32-32s14.3-32 32-32l83.1 0C103 204.6 96 181.8 96 157.5zM349.2 336l65.5 0c.9 6.1 1.4 12.2 1.4 18.5 0 69.3-56.2 125.5-125.5 125.5L144 480c-17.7 0-32-14.3-32-32s14.3-32 32-32l146.5 0c34 0 61.5-27.5 61.5-61.5 0-6.4-1-12.7-2.8-18.5z"/></svg>`,
		subscript: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 64C78.3 64 64 78.3 64 96s14.3 32 32 32l15.3 0 89.6 128-89.6 128-15.3 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l32 0c10.4 0 20.2-5.1 26.2-13.6L240 311.8 325.8 434.4c6 8.6 15.8 13.6 26.2 13.6l32 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-15.3 0-89.6-128 89.6-128 15.3 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-32 0c-10.4 0-20.2 5.1-26.2 13.6L240 200.2 154.2 77.6C148.2 69.1 138.4 64 128 64L96 64zM544 320c0-11.1-5.7-21.4-15.2-27.2s-21.2-6.4-31.1-1.4l-32 16c-15.8 7.9-22.2 27.1-14.3 42.9 5.6 11.2 16.9 17.7 28.6 17.7l0 80c-17.7 0-32 14.3-32 32s14.3 32 32 32l64 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l0-128z"/></svg>`,
		superscript: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M544 32c0-11.1-5.7-21.4-15.2-27.2s-21.2-6.4-31.1-1.4l-32 16C449.9 27.3 443.5 46.5 451.4 62.3 457 73.5 468.3 80 480 80l0 80c-17.7 0-32 14.3-32 32s14.3 32 32 32l64 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l0-128zM96 64C78.3 64 64 78.3 64 96s14.3 32 32 32l15.3 0 89.6 128-89.6 128-15.3 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l32 0c10.4 0 20.2-5.1 26.2-13.6L240 311.8 325.8 434.4c6 8.6 15.8 13.6 26.2 13.6l32 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-15.3 0-89.6-128 89.6-128 15.3 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-32 0c-10.4 0-20.2 5.1-26.2 13.6L240 200.2 154.2 77.6C148.2 69.1 138.4 64 128 64L96 64z"/></svg>`,
		table: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M384 32c35.3 0 64 28.7 64 64l0 320c0 35.3-28.7 64-64 64l-320 0-6.5-.3C25.2 476.4 0 449.1 0 416L0 96C0 60.7 28.7 32 64 32l320 0zM64 320l0 96 128 0 0-96-128 0zm192 0l0 96 128 0 0-96-128 0zM64 256l128 0 0-96-128 0 0 96zm192 0l128 0 0-96-128 0 0 96z"/></svg>`,
		"table-cells": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M384 96l0 64-64 0 0-64 64 0zm0 128l0 64-64 0 0-64 64 0zm0 128l0 64-64 0 0-64 64 0zM256 288l-64 0 0-64 64 0 0 64zm-64 64l64 0 0 64-64 0 0-64zm-64-64l-64 0 0-64 64 0 0 64zM64 352l64 0 0 64-64 0 0-64zm0-192l0-64 64 0 0 64-64 0zm128 0l0-64 64 0 0 64-64 0zM64 32C28.7 32 0 60.7 0 96L0 416c0 35.3 28.7 64 64 64l320 0c35.3 0 64-28.7 64-64l0-320c0-35.3-28.7-64-64-64L64 32z"/></svg>`,
		"table-cells-large": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M384 96l-128 0 0 128 128 0 0-128zm64 128l0 192c0 35.3-28.7 64-64 64L64 480c-35.3 0-64-28.7-64-64L0 96C0 60.7 28.7 32 64 32l320 0c35.3 0 64 28.7 64 64l0 128zM64 288l0 128 128 0 0-128-128 0zm128-64l0-128-128 0 0 128 128 0zm64 64l0 128 128 0 0-128-128 0z"/></svg>`,
		"table-columns": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 96C0 60.7 28.7 32 64 32l320 0c35.3 0 64 28.7 64 64l0 320c0 35.3-28.7 64-64 64L64 480c-35.3 0-64-28.7-64-64L0 96zm64 64l0 256 128 0 0-256-128 0zm320 0l-128 0 0 256 128 0 0-256z"/></svg>`,
		"text-slash": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M41-24.9c-9.4-9.4-24.6-9.4-33.9 0S-2.3-.3 7 9.1l528 528c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9L322.7 256.9 368.2 96 471 96 465 120.2c-4.3 17.1 6.1 34.5 23.3 38.8s34.5-6.1 38.8-23.3l11-44.1C545.6 61.3 522.7 32 491.5 32l-319 0c-19.8 0-37.3 12.1-44.5 30.1l-87-87zM180.4 114.5l4.6-18.5 116.7 0-30.8 109-90.5-90.5zM241 310.8L211.3 416 160 416c-17.7 0-32 14.3-32 32s14.3 32 32 32l160 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-42.2 0 15.1-53.3-51.9-51.9z"/></svg>`,
		thumbtack: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M32 32C32 14.3 46.3 0 64 0L320 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-29.5 0 10.3 134.1c37.1 21.2 65.8 56.4 78.2 99.7l3.8 13.4c2.8 9.7 .8 20-5.2 28.1S362 352 352 352L32 352c-10 0-19.5-4.7-25.5-12.7s-8-18.4-5.2-28.1L5 297.8c12.4-43.3 41-78.5 78.2-99.7L93.5 64 64 64C46.3 64 32 49.7 32 32zM160 400l64 0 0 112c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-112z"/></svg>`,
		trash: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M136.7 5.9L128 32 32 32C14.3 32 0 46.3 0 64S14.3 96 32 96l384 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-96 0-8.7-26.1C306.9-7.2 294.7-16 280.9-16L167.1-16c-13.8 0-26 8.8-30.4 21.9zM416 144L32 144 53.1 467.1C54.7 492.4 75.7 512 101 512L347 512c25.3 0 46.3-19.6 47.9-44.9L416 144z"/></svg>`,
		underline: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 32C0 14.3 14.3 0 32 0L96 0c17.7 0 32 14.3 32 32S113.7 64 96 64l0 160c0 53 43 96 96 96s96-43 96-96l0-160c-17.7 0-32-14.3-32-32S270.3 0 288 0l64 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l0 160c0 88.4-71.6 160-160 160S32 312.4 32 224L32 64C14.3 64 0 49.7 0 32zM0 480c0-17.7 14.3-32 32-32l320 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 512c-17.7 0-32-14.3-32-32z"/></svg>`,
		"up-down": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M406.6 502.6l96-96c9.2-9.2 11.9-22.9 6.9-34.9S492.9 352 480 352l-64 0 0-320c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 320-64 0c-12.9 0-24.6 7.8-29.6 19.8s-2.2 25.7 6.9 34.9l96 96c12.5 12.5 32.8 12.5 45.3 0zM150.6 9.4c-12.5-12.5-32.8-12.5-45.3 0l-96 96c-9.2 9.2-11.9 22.9-6.9 34.9S19.1 160 32 160l64 0 0 320c0 17.7 14.3 32 32 32s32-14.3 32-32l0-320 64 0c12.9 0 24.6-7.8 29.6-19.8s2.2-25.7-6.9-34.9l-96-96z"/></svg>`,
		upload: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M352 173.3L352 384C352 401.7 337.7 416 320 416C302.3 416 288 401.7 288 384L288 173.3L246.6 214.7C234.1 227.2 213.8 227.2 201.3 214.7C188.8 202.2 188.8 181.9 201.3 169.4L297.3 73.4C309.8 60.9 330.1 60.9 342.6 73.4L438.6 169.4C451.1 181.9 451.1 202.2 438.6 214.7C426.1 227.2 405.8 227.2 393.3 214.7L352 173.3zM320 464C364.2 464 400 428.2 400 384L480 384C515.3 384 544 412.7 544 448L544 480C544 515.3 515.3 544 480 544L160 544C124.7 544 96 515.3 96 480L96 448C96 412.7 124.7 384 160 384L240 384C240 428.2 275.8 464 320 464zM464 488C477.3 488 488 477.3 488 464C488 450.7 477.3 440 464 440C450.7 440 440 450.7 440 464C440 477.3 450.7 488 464 488z"/></svg>`,
		user: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M224 248a120 120 0 1 0 0-240 120 120 0 1 0 0 240zm-29.7 56C95.8 304 16 383.8 16 482.3 16 498.7 29.3 512 45.7 512l356.6 0c16.4 0 29.7-13.3 29.7-29.7 0-98.5-79.8-178.3-178.3-178.3l-59.4 0z"/></svg>`,
		volume: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM441.1 107c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C443.3 170.7 464 210.9 464 256s-20.7 85.3-53.2 111.8c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5c43.2-35.2 70.9-88.9 70.9-149s-27.7-113.8-70.9-149zm-60.5 74.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C361.1 227.6 368 241 368 256s-6.9 28.4-17.7 37.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C402.1 312.9 416 286.1 416 256s-13.9-56.9-35.5-74.5z"/></svg>`,
		"volume-low": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM380.6 181.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C361.1 227.6 368 241 368 256s-6.9 28.4-17.7 37.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C402.1 312.9 416 286.1 416 256s-13.9-56.9-35.5-74.5z"/></svg>`,
		"volume-xmark": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM367 175c-9.4 9.4-9.4 24.6 0 33.9l47 47-47 47c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l47-47 47 47c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-47-47 47-47c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-47 47-47-47c-9.4-9.4-24.6-9.4-33.9 0z"/></svg>`,
		xmark: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M55.1 73.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L147.2 256 9.9 393.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L192.5 301.3 329.9 438.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L237.8 256 375.1 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L192.5 210.7 55.1 73.4z"/></svg>`
	},
	regular: {
		calendar: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M216 64C229.3 64 240 74.7 240 88L240 128L400 128L400 88C400 74.7 410.7 64 424 64C437.3 64 448 74.7 448 88L448 128L480 128C515.3 128 544 156.7 544 192L544 480C544 515.3 515.3 544 480 544L160 544C124.7 544 96 515.3 96 480L96 192C96 156.7 124.7 128 160 128L192 128L192 88C192 74.7 202.7 64 216 64zM216 176L160 176C151.2 176 144 183.2 144 192L144 240L496 240L496 192C496 183.2 488.8 176 480 176L216 176zM144 288L144 480C144 488.8 151.2 496 160 496L480 496C488.8 496 496 488.8 496 480L496 288L144 288z"/></svg>`,
		"circle-question": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M464 256a208 208 0 1 0 -416 0 208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0zm256-80c-17.7 0-32 14.3-32 32 0 13.3-10.7 24-24 24s-24-10.7-24-24c0-44.2 35.8-80 80-80s80 35.8 80 80c0 47.2-36 67.2-56 74.5l0 3.8c0 13.3-10.7 24-24 24s-24-10.7-24-24l0-8.1c0-20.5 14.8-35.2 30.1-40.2 6.4-2.1 13.2-5.5 18.2-10.3 4.3-4.2 7.7-10 7.7-19.6 0-17.7-14.3-32-32-32zM224 368a32 32 0 1 1 64 0 32 32 0 1 1 -64 0z"/></svg>`,
		"circle-xmark": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464a256 256 0 1 0 0-512 256 256 0 1 0 0 512zM167 167c-9.4 9.4-9.4 24.6 0 33.9l55 55-55 55c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l55-55 55 55c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-55-55 55-55c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-55 55-55-55c-9.4-9.4-24.6-9.4-33.9 0z"/></svg>`,
		clock: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M528 320C528 434.9 434.9 528 320 528C205.1 528 112 434.9 112 320C112 205.1 205.1 112 320 112C434.9 112 528 205.1 528 320zM64 320C64 461.4 178.6 576 320 576C461.4 576 576 461.4 576 320C576 178.6 461.4 64 320 64C178.6 64 64 178.6 64 320zM296 184L296 320C296 328 300 335.5 306.7 340L402.7 404C413.7 411.4 428.6 408.4 436 397.3C443.4 386.2 440.4 371.4 429.3 364L344 307.2L344 184C344 170.7 333.3 160 320 160C306.7 160 296 170.7 296 184z"/></svg>`,
		copy: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M384 336l-192 0c-8.8 0-16-7.2-16-16l0-256c0-8.8 7.2-16 16-16l133.5 0c4.2 0 8.3 1.7 11.3 4.7l58.5 58.5c3 3 4.7 7.1 4.7 11.3L400 320c0 8.8-7.2 16-16 16zM192 384l192 0c35.3 0 64-28.7 64-64l0-197.5c0-17-6.7-33.3-18.7-45.3L370.7 18.7C358.7 6.7 342.5 0 325.5 0L192 0c-35.3 0-64 28.7-64 64l0 256c0 35.3 28.7 64 64 64zM64 128c-35.3 0-64 28.7-64 64L0 448c0 35.3 28.7 64 64 64l192 0c35.3 0 64-28.7 64-64l0-16-48 0 0 16c0 8.8-7.2 16-16 16L64 464c-8.8 0-16-7.2-16-16l0-256c0-8.8 7.2-16 16-16l16 0 0-48-16 0z"/></svg>`,
		eye: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M288 80C222.8 80 169.2 109.6 128.1 147.7 89.6 183.5 63 226 49.4 256 63 286 89.6 328.5 128.1 364.3 169.2 402.4 222.8 432 288 432s118.8-29.6 159.9-67.7C486.4 328.5 513 286 526.6 256 513 226 486.4 183.5 447.9 147.7 406.8 109.6 353.2 80 288 80zM95.4 112.6C142.5 68.8 207.2 32 288 32s145.5 36.8 192.6 80.6c46.8 43.5 78.1 95.4 93 131.1 3.3 7.9 3.3 16.7 0 24.6-14.9 35.7-46.2 87.7-93 131.1-47.1 43.7-111.8 80.6-192.6 80.6S142.5 443.2 95.4 399.4c-46.8-43.5-78.1-95.4-93-131.1-3.3-7.9-3.3-16.7 0-24.6 14.9-35.7 46.2-87.7 93-131.1zM288 336c44.2 0 80-35.8 80-80 0-29.6-16.1-55.5-40-69.3-1.4 59.7-49.6 107.9-109.3 109.3 13.8 23.9 39.7 40 69.3 40zm-79.6-88.4c2.5 .3 5 .4 7.6 .4 35.3 0 64-28.7 64-64 0-2.6-.2-5.1-.4-7.6-37.4 3.9-67.2 33.7-71.1 71.1zm45.6-115c10.8-3 22.2-4.5 33.9-4.5 8.8 0 17.5 .9 25.8 2.6 .3 .1 .5 .1 .8 .2 57.9 12.2 101.4 63.7 101.4 125.2 0 70.7-57.3 128-128 128-61.6 0-113-43.5-125.2-101.4-1.8-8.6-2.8-17.5-2.8-26.6 0-11 1.4-21.8 4-32 .2-.7 .3-1.3 .5-1.9 11.9-43.4 46.1-77.6 89.5-89.5z"/></svg>`,
		"eye-slash": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M41-24.9c-9.4-9.4-24.6-9.4-33.9 0S-2.3-.3 7 9.1l528 528c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-96.4-96.4c2.7-2.4 5.4-4.8 8-7.2 46.8-43.5 78.1-95.4 93-131.1 3.3-7.9 3.3-16.7 0-24.6-14.9-35.7-46.2-87.7-93-131.1-47.1-43.7-111.8-80.6-192.6-80.6-56.8 0-105.6 18.2-146 44.2L41-24.9zM176.9 111.1c32.1-18.9 69.2-31.1 111.1-31.1 65.2 0 118.8 29.6 159.9 67.7 38.5 35.7 65.1 78.3 78.6 108.3-13.6 30-40.2 72.5-78.6 108.3-3.1 2.8-6.2 5.6-9.4 8.4L393.8 328c14-20.5 22.2-45.3 22.2-72 0-70.7-57.3-128-128-128-26.7 0-51.5 8.2-72 22.2l-39.1-39.1zm182 182l-108-108c11.1-5.8 23.7-9.1 37.1-9.1 44.2 0 80 35.8 80 80 0 13.4-3.3 26-9.1 37.1zM103.4 173.2l-34-34c-32.6 36.8-55 75.8-66.9 104.5-3.3 7.9-3.3 16.7 0 24.6 14.9 35.7 46.2 87.7 93 131.1 47.1 43.7 111.8 80.6 192.6 80.6 37.3 0 71.2-7.9 101.5-20.6L352.2 422c-20 6.4-41.4 10-64.2 10-65.2 0-118.8-29.6-159.9-67.7-38.5-35.7-65.1-78.3-78.6-108.3 10.4-23.1 28.6-53.6 54-82.8z"/></svg>`,
		star: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M288.1-32c9 0 17.3 5.1 21.4 13.1L383 125.3 542.9 150.7c8.9 1.4 16.3 7.7 19.1 16.3s.5 18-5.8 24.4L441.7 305.9 467 465.8c1.4 8.9-2.3 17.9-9.6 23.2s-17 6.1-25 2L288.1 417.6 143.8 491c-8 4.1-17.7 3.3-25-2s-11-14.2-9.6-23.2L134.4 305.9 20 191.4c-6.4-6.4-8.6-15.8-5.8-24.4s10.1-14.9 19.1-16.3l159.9-25.4 73.6-144.2c4.1-8 12.4-13.1 21.4-13.1zm0 76.8L230.3 158c-3.5 6.8-10 11.6-17.6 12.8l-125.5 20 89.8 89.9c5.4 5.4 7.9 13.1 6.7 20.7l-19.8 125.5 113.3-57.6c6.8-3.5 14.9-3.5 21.8 0l113.3 57.6-19.8-125.5c-1.2-7.6 1.3-15.3 6.7-20.7l89.8-89.9-125.5-20c-7.6-1.2-14.1-6-17.6-12.8L288.1 44.8z"/></svg>`
	}
};
var loadedSets = /* @__PURE__ */ new Map();
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.BC3PCNTX.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var registry = [library_default_default, {
	name: "system",
	resolver: (name, _family = "classic", variant = "solid") => {
		const resolve = (set2) => {
			const svg = set2?.[variant]?.[name] ?? (icons[variant] ?? icons.solid)[name] ?? icons.regular[name] ?? icons.regular["circle-question"];
			return svg ? dataUri(svg) : "";
		};
		const folder = getIconFolder(name, getDefaultIconFamily(), getDefaultIconVariant());
		const loader = systemIconSets[folder];
		if (!loader) return resolve();
		let set = loadedSets.get(folder);
		if (!set) {
			set = loader().then((module) => module.default, () => void 0);
			loadedSets.set(folder, set);
		}
		return set.then(resolve);
	},
	mutator: (svg) => {
		if (!svg.hasAttribute("fill")) svg.setAttribute("fill", "currentColor");
	}
}];
var watchedIcons = /* @__PURE__ */ new Set();
function watchIcon(icon) {
	watchedIcons.add(icon);
}
function unwatchIcon(icon) {
	watchedIcons.delete(icon);
}
function getIconLibrary(name) {
	return registry.find((lib) => lib.name === name);
}
// node_modules/lit-html/directive-helpers.js
/**
* @license
* Copyright 2020 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var { I: t } = j$1, i$1 = (o) => o, l$1 = (o, t) => void 0 === t ? void 0 !== o?._$litType$ : o?._$litType$ === t, r$1 = (o) => void 0 === o.strings, s = () => document.createComment(""), v = (o, n, e) => {
	const l = o._$AA.parentNode, d = void 0 === n ? o._$AB : n._$AA;
	if (void 0 === e) e = new t(l.insertBefore(s(), d), l.insertBefore(s(), d), o, o.options);
	else {
		const t = e._$AB.nextSibling, n = e._$AM, c = n !== o;
		if (c) {
			let t;
			e._$AQ?.(o), e._$AM = o, void 0 !== e._$AP && (t = o._$AU) !== n._$AU && e._$AP(t);
		}
		if (t !== d || c) {
			let o = e._$AA;
			for (; o !== t;) {
				const t = i$1(o).nextSibling;
				i$1(l).insertBefore(o, d), o = t;
			}
		}
	}
	return e;
}, u$1 = (o, t, i = o) => (o._$AI(t, i), o), m = {}, p = (o, t = m) => o._$AH = t, M = (o) => o._$AH, h = (o) => {
	o._$AR(), o._$AA.remove();
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.N556ZCKP.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var CACHEABLE_ERROR = Symbol();
var RETRYABLE_ERROR = Symbol();
var parser;
var iconCache = /* @__PURE__ */ new Map();
var WaIcon = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.svg = null;
		this.autoWidth = false;
		this.swapOpacity = false;
		this.label = "";
		this.library = "default";
		this.rotate = 0;
		/** Given a URL, this function returns the resulting SVG element or an appropriate error symbol. */
		this.resolveIcon = async (url, library) => {
			let fileData;
			if (library?.spriteSheet) {
				if (!this.hasUpdated) await this.updateComplete;
				this.svg = b`<svg part="svg">
        <use part="use" href="${url}"></use>
      </svg>`;
				await this.updateComplete;
				const svg = this.shadowRoot.querySelector("[part='svg']");
				if (typeof library.mutator === "function") library.mutator(svg, this);
				return this.svg;
			}
			try {
				fileData = await fetch(url, { mode: "cors" });
				if (!fileData.ok) return fileData.status === 410 ? CACHEABLE_ERROR : RETRYABLE_ERROR;
			} catch {
				return RETRYABLE_ERROR;
			}
			try {
				const div = document.createElement("div");
				div.innerHTML = await fileData.text();
				const svg = div.firstElementChild;
				if (svg?.tagName?.toLowerCase() !== "svg") return CACHEABLE_ERROR;
				if (!parser) parser = new DOMParser();
				const svgEl = parser.parseFromString(svg.outerHTML, "text/html").body.querySelector("svg");
				if (!svgEl) return CACHEABLE_ERROR;
				svgEl.part.add("svg");
				return document.adoptNode(svgEl);
			} catch {
				return CACHEABLE_ERROR;
			}
		};
	}
	connectedCallback() {
		super.connectedCallback();
		watchIcon(this);
	}
	firstUpdated(changedProperties) {
		super.firstUpdated(changedProperties);
		if (this.hasAttribute("rotate")) this.style.setProperty("--rotate-angle", `${this.rotate}deg`);
		this.setIcon();
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		unwatchIcon(this);
	}
	async getIconSource() {
		const library = getIconLibrary(this.library);
		const family = this.family || getDefaultIconFamily();
		if (this.name && library) {
			const autoWidth = this.canvas === "auto" || this.autoWidth;
			let url;
			try {
				url = await library.resolver(this.name, family, this.variant, autoWidth);
			} catch {
				url = void 0;
			}
			return {
				url,
				fromLibrary: true
			};
		}
		return {
			url: this.src,
			fromLibrary: false
		};
	}
	handleLabelChange() {
		if (typeof this.label === "string" && this.label.length > 0) {
			this.setAttribute("role", "img");
			this.setAttribute("aria-label", this.label);
			this.removeAttribute("aria-hidden");
		} else {
			this.removeAttribute("role");
			this.removeAttribute("aria-label");
			this.setAttribute("aria-hidden", "true");
		}
	}
	async setIcon() {
		const { url, fromLibrary } = await this.getIconSource();
		const library = fromLibrary ? getIconLibrary(this.library) : void 0;
		if (!url) {
			this.svg = null;
			return;
		}
		let iconResolver = iconCache.get(url);
		if (!iconResolver) {
			iconResolver = this.resolveIcon(url, library);
			iconCache.set(url, iconResolver);
		}
		const svg = await iconResolver;
		if (svg === RETRYABLE_ERROR) iconCache.delete(url);
		if (url !== (await this.getIconSource()).url) return;
		if (l$1(svg)) {
			this.svg = svg;
			return;
		}
		switch (svg) {
			case RETRYABLE_ERROR:
			case CACHEABLE_ERROR:
				this.svg = null;
				this.dispatchEvent(new WaErrorEvent());
				break;
			default:
				this.svg = svg.cloneNode(true);
				library?.mutator?.(this.svg, this);
				this.dispatchEvent(new WaLoadEvent());
		}
	}
	willUpdate(changedProperties) {
		if (!this.style) this.setStyleProperty("--rotate-angle", `${this.rotate}deg`);
		return super.willUpdate(changedProperties);
	}
	updated(changedProperties) {
		super.updated(changedProperties);
		const library = getIconLibrary(this.library);
		if (this.hasAttribute("rotate")) this.style.setProperty("--rotate-angle", `${this.rotate}deg`);
		const svg = this.shadowRoot?.querySelector("svg");
		if (svg) library?.mutator?.(svg, this);
	}
	render() {
		if (this.hasUpdated) return this.svg;
		return b`<svg part="svg" width="16" height="16" viewBox="0 0 16 16"></svg>`;
	}
};
WaIcon.css = icon_styles_default;
__decorateClass([r$2()], WaIcon.prototype, "svg", 2);
__decorateClass([n$2({ reflect: true })], WaIcon.prototype, "name", 2);
__decorateClass([n$2({ reflect: true })], WaIcon.prototype, "family", 2);
__decorateClass([n$2({ reflect: true })], WaIcon.prototype, "variant", 2);
__decorateClass([n$2({ reflect: true })], WaIcon.prototype, "canvas", 2);
__decorateClass([n$2({
	attribute: "auto-width",
	type: Boolean,
	reflect: true
})], WaIcon.prototype, "autoWidth", 2);
__decorateClass([n$2({
	attribute: "swap-opacity",
	type: Boolean,
	reflect: true
})], WaIcon.prototype, "swapOpacity", 2);
__decorateClass([n$2()], WaIcon.prototype, "src", 2);
__decorateClass([n$2()], WaIcon.prototype, "label", 2);
__decorateClass([n$2({ reflect: true })], WaIcon.prototype, "library", 2);
__decorateClass([n$2({
	type: Number,
	reflect: true
})], WaIcon.prototype, "rotate", 2);
__decorateClass([n$2({
	type: String,
	reflect: true
})], WaIcon.prototype, "flip", 2);
__decorateClass([n$2({
	type: String,
	reflect: true
})], WaIcon.prototype, "animation", 2);
__decorateClass([watch("label")], WaIcon.prototype, "handleLabelChange", 1);
__decorateClass([watch([
	"family",
	"name",
	"library",
	"variant",
	"src",
	"autoWidth",
	"canvas",
	"swapOpacity"
], { waitUntilFirstUpdate: true })], WaIcon.prototype, "setIcon", 1);
WaIcon = __decorateClass([t$2("wa-icon")], WaIcon);
// node_modules/@awesome.me/webawesome/dist/components/button/button.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.ATI2KDM5.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var card_styles_default = i$7`
  :host {
    --spacing: var(--wa-space-l);

    /* Internal calculated properties */
    --inner-border-radius: calc(var(--wa-panel-border-radius) - var(--wa-panel-border-width));

    display: flex;
    flex-direction: column;
    background-color: var(--wa-color-surface-default);
    border-color: var(--wa-color-surface-border);
    border-radius: var(--wa-panel-border-radius);
    border-style: var(--wa-panel-border-style);
    box-shadow: var(--wa-shadow-s);
    border-width: var(--wa-panel-border-width);
    color: var(--wa-color-text-normal);
  }

  /* Appearance modifiers */
  :host([appearance='plain']) {
    background-color: transparent;
    border-color: transparent;
    box-shadow: none;
  }

  :host([appearance='outlined']) {
    background-color: var(--wa-color-surface-default);
    border-color: var(--wa-color-surface-border);
  }

  :host([appearance='filled']) {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: transparent;
  }

  :host([appearance='filled-outlined']) {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-surface-border);
  }

  :host([appearance='accent']) {
    color: var(--wa-color-neutral-on-loud);
    background-color: var(--wa-color-neutral-fill-loud);
    border-color: transparent;
  }

  /* Take care of top and bottom radii */
  .media,
  :host(:not([with-media])) .header,
  :host(:not([with-media], [with-header])) .body {
    border-start-start-radius: var(--inner-border-radius);
    border-start-end-radius: var(--inner-border-radius);
  }

  :host(:not([with-footer])) .body,
  .footer {
    border-end-start-radius: var(--inner-border-radius);
    border-end-end-radius: var(--inner-border-radius);
  }

  .media {
    display: flex;
    overflow: hidden;

    &::slotted(*) {
      display: block;
      width: 100%;
      border-radius: 0 !important;
    }
  }

  /* Round all corners for plain appearance */
  :host([appearance='plain']) .media {
    border-radius: var(--inner-border-radius);

    &::slotted(*) {
      border-radius: inherit !important;
    }
  }

  .header {
    display: block;
    border-block-end-style: inherit;
    border-block-end-color: var(--wa-color-surface-border);
    border-block-end-width: var(--wa-panel-border-width);
    padding: calc(var(--spacing) / 2) var(--spacing);
  }

  .body {
    display: block;
    padding: var(--spacing);
  }

  .footer {
    display: block;
    border-block-start-style: inherit;
    border-block-start-color: var(--wa-color-surface-border);
    border-block-start-width: var(--wa-panel-border-width);
    padding: var(--spacing);
  }

  /* Push slots to sides when the action slots renders */
  .has-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  :host(:not([with-header])) .header,
  :host(:not([with-footer])) .footer,
  :host(:not([with-media])) .media {
    display: none;
  }

  /* Orientation Styles */
  :host([orientation='horizontal']) {
    flex-direction: row;

    .media {
      border-start-start-radius: var(--inner-border-radius);
      border-end-start-radius: var(--inner-border-radius);
      border-start-end-radius: 0;

      &::slotted(*) {
        block-size: 100%;
        inline-size: 100%;
        object-fit: cover;
      }
    }
  }

  :host([orientation='horizontal']) .body slot::slotted(*) {
    display: block;
    height: 100%;
    margin: 0;
  }

  :host([orientation='horizontal']) slot[name='actions']::slotted(*) {
    display: flex;
    align-items: center;
    padding: var(--spacing);
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.YKC4SGGJ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaCard = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.hasSlotController = new HasSlotController(this, "footer", "header", "media", "header-actions", "footer-actions", "actions");
		this.appearance = "outlined";
		this.withHeader = false;
		this.withMedia = false;
		this.withFooter = false;
		this.withHeaderActions = false;
		this.withFooterActions = false;
		this.orientation = "vertical";
	}
	willUpdate(changedProperties) {
		this.withHeader = this.hasSlotController.test("header", "withHeader");
		this.withMedia = this.hasSlotController.test("media", "withMedia");
		this.withFooter = this.hasSlotController.test("footer", "withFooter");
		super.willUpdate(changedProperties);
	}
	render() {
		if (this.orientation === "horizontal") return b`
        <slot name="media" part="media" class="media"></slot>
        <div part="body" class="body"><slot></slot></div>
        <slot name="actions" part="actions" class="actions"></slot>
      `;
		const hasHeaderActions = this.hasSlotController.test("header-actions", "withHeaderActions");
		const hasFooterActions = this.hasSlotController.test("footer-actions", "withFooterActions");
		return b`
      <slot name="media" part="media" class="media"></slot>

      <div
        part="header"
        class=${e$3({
			header: true,
			"has-actions": hasHeaderActions
		})}
      >
        <slot name="header"></slot>
        <slot name="header-actions"></slot>
      </div>

      <div part="body" class="body"><slot></slot></div>

      <div
        part="footer"
        class=${e$3({
			footer: true,
			"has-actions": hasFooterActions
		})}
      >
        <slot name="footer"></slot>
        <slot name="footer-actions"></slot>
      </div>
    `;
	}
};
WaCard.css = [size_styles_default, card_styles_default];
__decorateClass([n$2({ reflect: true })], WaCard.prototype, "appearance", 2);
__decorateClass([n$2({
	attribute: "with-header",
	type: Boolean,
	reflect: true
})], WaCard.prototype, "withHeader", 2);
__decorateClass([n$2({
	attribute: "with-media",
	type: Boolean,
	reflect: true
})], WaCard.prototype, "withMedia", 2);
__decorateClass([n$2({
	attribute: "with-footer",
	type: Boolean,
	reflect: true
})], WaCard.prototype, "withFooter", 2);
__decorateClass([n$2({
	attribute: "with-header-actions",
	type: Boolean,
	reflect: true
})], WaCard.prototype, "withHeaderActions", 2);
__decorateClass([n$2({
	attribute: "with-footer-actions",
	type: Boolean,
	reflect: true
})], WaCard.prototype, "withFooterActions", 2);
__decorateClass([n$2({ reflect: true })], WaCard.prototype, "orientation", 2);
WaCard = __decorateClass([t$2("wa-card")], WaCard);
WaCard.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/components/card/card.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.W62SLQ7P.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var details_styles_default = i$7`
  :host {
    --spacing: var(--wa-space-m);
    --show-duration: var(--wa-transition-normal);
    --hide-duration: var(--wa-transition-normal);

    display: block;
  }

  details {
    display: block;
    overflow-anchor: none;
    border: var(--wa-panel-border-width) var(--wa-color-surface-border) var(--wa-panel-border-style);
    background-color: var(--wa-color-surface-default);
    border-radius: var(--wa-panel-border-radius);
    color: var(--wa-color-text-normal);

    /* Print styles */
    @media print {
      background: none;
      border: solid var(--wa-border-width-s) var(--wa-color-surface-border);

      summary {
        list-style: none;
      }
    }
  }

  /* Appearance modifiers */
  :host([appearance='plain']) details {
    background-color: transparent;
    border-color: transparent;
    border-radius: 0;
  }

  :host([appearance='outlined']) details {
    background-color: var(--wa-color-surface-default);
    border-color: var(--wa-color-surface-border);
  }

  :host([appearance='filled']) details {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: transparent;
  }

  :host([appearance='filled-outlined']) details {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-border-quiet);
  }

  :host([disabled]) details {
    opacity: 0.5;
    cursor: not-allowed;
  }

  summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing);
    padding: var(--spacing); /* Add padding here */
    border-radius: calc(var(--wa-panel-border-radius) - var(--wa-panel-border-width));
    user-select: none;
    -webkit-user-select: none;
    cursor: pointer;

    &::marker,
    &::-webkit-details-marker {
      display: none;
    }

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: calc(var(--wa-panel-border-width) + var(--wa-focus-ring-offset));
    }
  }

  :host([open]) summary {
    border-end-start-radius: 0;
    border-end-end-radius: 0;
  }

  /* 'Start' icon placement */
  :host([icon-placement='start']) summary {
    flex-direction: row-reverse;
    justify-content: start;
  }

  [part~='icon'] {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    color: var(--wa-color-text-quiet);
    transition: rotate var(--wa-transition-normal) var(--wa-transition-easing);
  }

  :host([open]) [part~='icon'] {
    rotate: 90deg;
  }

  :host([open]:dir(rtl)) [part~='icon'] {
    rotate: -90deg;
  }

  :host([open]) slot[name='expand-icon'],
  :host(:not([open])) slot[name='collapse-icon'] {
    display: none;
  }

  .body.animating {
    overflow: hidden;
  }

  .content {
    display: block;
    box-sizing: border-box; /* Ensure contents don't overflow */
    padding-block-start: var(--spacing);
    padding-inline: var(--spacing); /* Add horizontal padding */
    padding-block-end: var(--spacing); /* Add bottom padding */
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.4ZAKP7NY.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaShowEvent = class extends Event {
	constructor() {
		super("wa-show", {
			bubbles: true,
			cancelable: true,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.MQODJ75V.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaHideEvent = class extends Event {
	constructor(detail) {
		super("wa-hide", {
			bubbles: true,
			cancelable: true,
			composed: true
		});
		this.detail = detail;
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.3NKIHICW.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaAfterHideEvent = class extends Event {
	constructor() {
		super("wa-after-hide", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.PX3HMKF7.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaAfterShowEvent = class extends Event {
	constructor() {
		super("wa-after-show", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.F25QOBDY.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function waitForEvent(el, eventName) {
	return new Promise((resolve) => {
		function done(event) {
			if (event.target === el) {
				el.removeEventListener(eventName, done);
				resolve();
			}
		}
		el.addEventListener(eventName, done);
	});
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.JATN5J6W.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
async function animate(el, keyframes, options) {
	return el.animate(keyframes, options).finished.catch(() => {});
}
async function animateWithClass(el, className) {
	el.getAnimations();
	el.classList.add(className);
	await new Promise((resolve) => requestAnimationFrame(() => resolve()));
	const animationPromises = [];
	for (const animation of el.getAnimations()) if (animation instanceof CSSAnimation && animation.effect?.getComputedTiming().endTime !== Infinity) animationPromises.push(animation.finished);
	await Promise.allSettled(animationPromises);
	el.classList.remove(className);
}
function parseDuration(duration) {
	duration = duration.toString().toLowerCase();
	if (duration.indexOf("ms") > -1) return parseFloat(duration) || 0;
	if (duration.indexOf("s") > -1) return (parseFloat(duration) || 0) * 1e3;
	return parseFloat(duration) || 0;
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.MW5BGCHS.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaDetails = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
		this.animationGeneration = 0;
		this.isAnimating = false;
		this.open = false;
		this.disabled = false;
		this.appearance = "outlined";
		this.iconPlacement = "end";
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		this.detailsObserver?.disconnect();
	}
	firstUpdated(changedProperties) {
		super.firstUpdated(changedProperties);
		this.body.style.height = this.open ? "auto" : "0";
		if (this.open) this.details.open = true;
		this.detailsObserver = new MutationObserver((changes) => {
			for (const change of changes) if (change.type === "attributes" && change.attributeName === "open") {
				if (this.details.open) this.show();
				else this.hide();
			}
		});
		this.detailsObserver.observe(this.details, { attributes: true });
	}
	updated(changedProperties) {
		if (changedProperties.has("isAnimating")) this.customStates.set("animating", this.isAnimating);
	}
	handleSummaryClick(event) {
		if (event.composedPath().some((element) => {
			if (!(element instanceof HTMLElement)) return false;
			const tagName = element.tagName?.toLowerCase();
			if ([
				"a",
				"button",
				"input",
				"textarea",
				"select"
			].includes(tagName)) return true;
			if (element instanceof WebAwesomeFormAssociatedElement) return !("disabled" in element) || !element.disabled;
			return false;
		})) return;
		event.preventDefault();
		if (!this.disabled) {
			if (this.open) this.hide();
			else this.show();
			this.header.focus();
		}
	}
	handleSummaryKeyDown(event) {
		if (event.key === "Enter" || event.key === " ") {
			event.preventDefault();
			if (this.open) this.hide();
			else this.show();
		}
		if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
			event.preventDefault();
			this.hide();
		}
		if (event.key === "ArrowDown" || event.key === "ArrowRight") {
			event.preventDefault();
			this.show();
		}
	}
	/** Closes other <wa-details> elements in the same document when they have the same name. */
	closeOthersWithSameName() {
		if (!this.name) return;
		this.getRootNode().querySelectorAll(`wa-details[name="${this.name}"]`).forEach((detail) => {
			if (detail !== this && detail.open) detail.open = false;
		});
	}
	async handleOpenChange() {
		this.animationGeneration++;
		const generation = this.animationGeneration;
		if (this.open) {
			this.details.open = true;
			const waShow = new WaShowEvent();
			this.dispatchEvent(waShow);
			if (waShow.defaultPrevented) {
				this.open = false;
				this.details.open = false;
				return;
			}
			this.closeOthersWithSameName();
			this.isAnimating = true;
			const duration = parseDuration(getComputedStyle(this.body).getPropertyValue("--show-duration"));
			const easing = getComputedStyle(this.body).getPropertyValue("--wa-transition-easing") || "ease";
			await animate(this.body, [{
				height: "0",
				opacity: "0"
			}, {
				height: `${this.body.scrollHeight}px`,
				opacity: "1"
			}], {
				duration,
				easing
			});
			if (this.animationGeneration !== generation) return;
			this.body.style.height = "auto";
			this.isAnimating = false;
			this.dispatchEvent(new WaAfterShowEvent());
		} else {
			const waHide = new WaHideEvent();
			this.dispatchEvent(waHide);
			if (waHide.defaultPrevented) {
				this.details.open = true;
				this.open = true;
				return;
			}
			this.isAnimating = true;
			const duration = parseDuration(getComputedStyle(this.body).getPropertyValue("--hide-duration"));
			const easing = getComputedStyle(this.body).getPropertyValue("--wa-transition-easing") || "ease";
			await animate(this.body, [{
				height: `${this.body.scrollHeight}px`,
				opacity: "1"
			}, {
				height: "0",
				opacity: "0"
			}], {
				duration,
				easing
			});
			if (this.animationGeneration !== generation) return;
			this.body.style.height = "0";
			this.isAnimating = false;
			this.details.open = false;
			this.dispatchEvent(new WaAfterHideEvent());
		}
	}
	/** Shows the details. */
	async show() {
		if (this.open || this.disabled) return;
		this.open = true;
		return waitForEvent(this, "wa-after-show");
	}
	/** Hides the details */
	async hide() {
		if (!this.open || this.disabled) return;
		this.open = false;
		return waitForEvent(this, "wa-after-hide");
	}
	render() {
		const isRtl = !this.hasUpdated ? this.dir === "rtl" : this.localize.dir() === "rtl";
		return b`
      <details part="base details">
        <summary
          part="header"
          role="button"
          aria-expanded=${this.open ? "true" : "false"}
          aria-controls="content"
          aria-disabled=${this.disabled ? "true" : "false"}
          tabindex=${this.disabled ? "-1" : "0"}
          @click=${this.handleSummaryClick}
          @keydown=${this.handleSummaryKeyDown}
        >
          <slot name="summary" part="summary">${this.summary}</slot>

          <span part="icon">
            <slot name="expand-icon">
              <wa-icon library="system" variant="solid" name=${isRtl ? "chevron-left" : "chevron-right"}></wa-icon>
            </slot>
            <slot name="collapse-icon">
              <wa-icon library="system" variant="solid" name=${isRtl ? "chevron-left" : "chevron-right"}></wa-icon>
            </slot>
          </span>
        </summary>

        <div
          class=${e$3({
			body: true,
			animating: this.isAnimating
		})}
          role="region"
          aria-labelledby="header"
        >
          <slot part="content" id="content" class="content"></slot>
        </div>
      </details>
    `;
	}
};
WaDetails.css = details_styles_default;
__decorateClass([e$5("details")], WaDetails.prototype, "details", 2);
__decorateClass([e$5("summary")], WaDetails.prototype, "header", 2);
__decorateClass([e$5(".body")], WaDetails.prototype, "body", 2);
__decorateClass([e$5(".expand-icon-slot")], WaDetails.prototype, "expandIconSlot", 2);
__decorateClass([r$2()], WaDetails.prototype, "isAnimating", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaDetails.prototype, "open", 2);
__decorateClass([n$2()], WaDetails.prototype, "summary", 2);
__decorateClass([n$2({ reflect: true })], WaDetails.prototype, "name", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaDetails.prototype, "disabled", 2);
__decorateClass([n$2({ reflect: true })], WaDetails.prototype, "appearance", 2);
__decorateClass([n$2({
	attribute: "icon-placement",
	reflect: true
})], WaDetails.prototype, "iconPlacement", 2);
__decorateClass([watch("open", { waitUntilFirstUpdate: true })], WaDetails.prototype, "handleOpenChange", 1);
WaDetails = __decorateClass([t$2("wa-details")], WaDetails);
// node_modules/@awesome.me/webawesome/dist/components/details/details.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.HKHINDC2.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var RenderedWatcher = class {
	constructor(element, callback) {
		this.element = element;
		this.callback = callback;
	}
	/**
	* Starts watching and reports the current state on the next frame. Additional targets also act as change signals,
	* e.g. an internal element that always has a non-zero box when rendered.
	*/
	start(...additionalTargets) {
		this.observer ?? (this.observer = new ResizeObserver(() => this.check()));
		this.observer.observe(this.element);
		for (const target of additionalTargets) this.observer.observe(target);
		this.initialCheckHandle ?? (this.initialCheckHandle = requestAnimationFrame(() => {
			this.initialCheckHandle = void 0;
			this.check();
		}));
	}
	/** Stops watching. */
	stop() {
		if (this.initialCheckHandle !== void 0) {
			cancelAnimationFrame(this.initialCheckHandle);
			this.initialCheckHandle = void 0;
		}
		this.observer?.disconnect();
	}
	check() {
		this.callback(this.element.getClientRects().length > 0);
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.DITA2S5A.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function getOffset(element, parent) {
	return {
		top: Math.round(element.getBoundingClientRect().top - parent.getBoundingClientRect().top),
		left: Math.round(element.getBoundingClientRect().left - parent.getBoundingClientRect().left)
	};
}
function isEventInsideRect(event, el) {
	const rect = el.getBoundingClientRect();
	return event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
}
var locks = /* @__PURE__ */ new Set();
function getScrollbarWidth() {
	const documentWidth = document.documentElement.clientWidth;
	return Math.abs(window.innerWidth - documentWidth);
}
function getExistingBodyPadding() {
	const padding = Number(getComputedStyle(document.body).paddingRight.replace(/px/, ""));
	if (isNaN(padding) || !padding) return 0;
	return padding;
}
function lockBodyScrolling(lockingEl) {
	locks.add(lockingEl);
	if (!document.documentElement.classList.contains("wa-scroll-lock")) {
		const scrollbarWidth = getScrollbarWidth() + getExistingBodyPadding();
		let scrollbarGutterProperty = getComputedStyle(document.documentElement).scrollbarGutter;
		if (!scrollbarGutterProperty || scrollbarGutterProperty === "auto") scrollbarGutterProperty = "stable";
		if (scrollbarWidth < 2) scrollbarGutterProperty = "";
		document.documentElement.style.setProperty("--wa-scroll-lock-gutter", scrollbarGutterProperty);
		document.documentElement.classList.add("wa-scroll-lock");
		document.documentElement.style.setProperty("--wa-scroll-lock-size", `${scrollbarWidth}px`);
	}
}
function unlockBodyScrolling(lockingEl) {
	locks.delete(lockingEl);
	if (locks.size === 0) {
		document.documentElement.classList.remove("wa-scroll-lock");
		document.documentElement.style.removeProperty("--wa-scroll-lock-size");
	}
}
function scrollIntoView(element, container, direction = "vertical", behavior = "smooth") {
	const offset = getOffset(element, container);
	const offsetTop = offset.top + container.scrollTop;
	const offsetLeft = offset.left + container.scrollLeft;
	const minX = container.scrollLeft;
	const maxX = container.scrollLeft + container.offsetWidth;
	const minY = container.scrollTop;
	const maxY = container.scrollTop + container.offsetHeight;
	if (direction === "horizontal" || direction === "both") {
		if (offsetLeft < minX) container.scrollTo({
			left: offsetLeft,
			behavior
		});
		else if (offsetLeft + element.clientWidth > maxX) container.scrollTo({
			left: offsetLeft - container.offsetWidth + element.clientWidth,
			behavior
		});
	}
	if (direction === "vertical" || direction === "both") {
		if (offsetTop < minY) container.scrollTo({
			top: offsetTop,
			behavior
		});
		else if (offsetTop + element.clientHeight > maxY) container.scrollTo({
			top: offsetTop - container.offsetHeight + element.clientHeight,
			behavior
		});
	}
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.RMZ7BVDM.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function parseSpaceDelimitedTokens(input) {
	return input.split(" ").map((token) => token.trim()).filter((token) => token !== "");
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.SP42P4TE.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var dialog_styles_default = i$7`
  :host {
    --width: 31rem;
    --spacing: var(--wa-space-l);
    --backdrop-color: var(--wa-color-overlay-modal);
    --backdrop-filter: none;
    --show-duration: var(--wa-transition-normal);
    --hide-duration: var(--wa-transition-normal);

    display: none;
  }

  :host([open]) {
    display: block;
  }

  .dialog {
    display: flex;
    flex-direction: column;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    width: var(--width);
    max-width: calc(100% - var(--wa-space-2xl));
    max-height: calc(100% - var(--wa-space-2xl));
    color: inherit;
    background-color: var(--wa-color-surface-raised);
    border-radius: var(--wa-panel-border-radius);
    border: none;
    box-shadow: var(--wa-shadow-l);
    padding: 0;
    margin: auto;

    &.show {
      animation: show-dialog var(--show-duration) ease;

      &::backdrop {
        animation: show-backdrop var(--show-duration, 200ms) ease;
      }
    }

    &.hide {
      animation: show-dialog var(--hide-duration) ease reverse;

      &::backdrop {
        animation: show-backdrop var(--hide-duration, 200ms) ease reverse;
      }
    }

    &.pulse {
      animation: pulse 250ms ease;
    }
  }

  .dialog:focus {
    outline: none;
  }

  /* Ensure there's enough vertical padding for phones that don't update vh when chrome appears (e.g. iPhone) */
  @media screen and (max-width: 420px) {
    .dialog {
      max-height: 80vh;
    }
  }

  .open {
    display: flex;
    opacity: 1;
  }

  .header {
    flex: 0 0 auto;
    display: flex;
    flex-wrap: nowrap;

    padding-inline-start: var(--spacing);
    padding-block-end: 0;

    /* Subtract the close button's padding so that the X is visually aligned with the edges of the dialog content */
    padding-inline-end: calc(var(--spacing) - var(--wa-form-control-padding-block));
    padding-block-start: calc(var(--spacing) - var(--wa-form-control-padding-block));
  }

  .title {
    align-self: center;
    flex: 1 1 auto;
    font-family: inherit;
    font-size: var(--wa-font-size-l);
    font-weight: var(--wa-font-weight-heading);
    line-height: var(--wa-line-height-condensed);
    margin: 0;
  }

  .header-actions {
    align-self: start;
    display: flex;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: end;
    gap: var(--wa-space-2xs);
    padding-inline-start: var(--spacing);
  }

  .header-actions wa-button,
  .header-actions ::slotted(wa-button) {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
  }

  .body {
    flex: 1 1 auto;
    display: block;
    padding: var(--spacing);
    overflow: auto;
    -webkit-overflow-scrolling: touch;

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: var(--wa-focus-ring-offset);
    }
  }

  .footer {
    flex: 0 0 auto;
    display: flex;
    flex-wrap: wrap;
    gap: var(--wa-space-xs);
    justify-content: end;
    padding: var(--spacing);
    padding-block-start: 0;
  }

  .footer ::slotted(wa-button:not(:first-of-type)) {
    margin-inline-start: var(--wa-spacing-xs);
  }

  .dialog::backdrop {
    /*
      NOTE: the ::backdrop element doesn't inherit properly in Safari yet, but it will in 17.4! At that time, we can
      remove the fallback values here.
    */
    background-color: var(--backdrop-color, rgb(0 0 0 / 0.25));
    backdrop-filter: var(--backdrop-filter);
  }

  @keyframes pulse {
    0% {
      scale: 1;
    }
    50% {
      scale: 1.02;
    }
    100% {
      scale: 1;
    }
  }

  @keyframes show-dialog {
    from {
      opacity: 0;
      scale: 0.8;
    }
    to {
      opacity: 1;
      scale: 1;
    }
  }

  @keyframes show-backdrop {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (forced-colors: active) {
    .dialog {
      border: solid 1px white;
    }
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.3H2FQERJ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var dismissibleStack = [];
function registerDismissible(key) {
	unregisterDismissible(key);
	dismissibleStack.push(key);
}
function unregisterDismissible(key) {
	for (let i = dismissibleStack.length - 1; i >= 0; i--) if (dismissibleStack[i] === key) {
		dismissibleStack.splice(i, 1);
		break;
	}
}
function isTopDismissible(key) {
	return dismissibleStack.length > 0 && dismissibleStack[dismissibleStack.length - 1] === key;
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.VEDZJMXI.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaDialog = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
		this.hasSlotController = new HasSlotController(this, "footer", "header-actions", "label");
		this.renderedWatcher = new RenderedWatcher(this, (isRendered) => this.handleRenderedChange(isRendered));
		this.open = false;
		this.label = "";
		this.withoutHeader = false;
		this.lightDismiss = false;
		this.withFooter = false;
		this.withLabel = false;
		this.handleDocumentKeyDown = (event) => {
			if (event.key === "Escape" && this.open && isTopDismissible(this)) {
				event.preventDefault();
				event.stopPropagation();
				this.requestClose(this.dialog);
			}
		};
	}
	firstUpdated(changedProperties) {
		super.firstUpdated(changedProperties);
		if (this.open) {
			this.addOpenListeners();
			this.dialog.showModal();
			lockBodyScrolling(this);
			this.renderedWatcher.start(this.dialog);
		}
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		this.renderedWatcher.stop();
		unlockBodyScrolling(this);
		this.removeOpenListeners();
	}
	async requestClose(source) {
		const waHideEvent = new WaHideEvent({ source });
		this.dispatchEvent(waHideEvent);
		if (waHideEvent.defaultPrevented) {
			this.open = true;
			animateWithClass(this.dialog, "pulse");
			return;
		}
		this.removeOpenListeners();
		await animateWithClass(this.dialog, "hide");
		this.open = false;
		this.dialog.close();
		unlockBodyScrolling(this);
		this.renderedWatcher.stop();
		const trigger = this.originalTrigger;
		if (typeof trigger?.focus === "function") setTimeout(() => trigger.focus());
		this.dispatchEvent(new WaAfterHideEvent());
	}
	addOpenListeners() {
		document.addEventListener("keydown", this.handleDocumentKeyDown);
		registerDismissible(this);
	}
	removeOpenListeners() {
		document.removeEventListener("keydown", this.handleDocumentKeyDown);
		unregisterDismissible(this);
	}
	handleDialogCancel(event) {
		event.preventDefault();
		if (!this.dialog.classList.contains("hide") && event.target === this.dialog && isTopDismissible(this)) this.requestClose(this.dialog);
	}
	handleDialogClick(event) {
		const button = event.target.closest("[data-dialog=\"close\"]");
		if (button) {
			event.stopPropagation();
			this.requestClose(button);
		}
	}
	async handleDialogPointerDown(event) {
		if (event.target === this.dialog && !isEventInsideRect(event, this.dialog)) {
			if (this.lightDismiss) this.requestClose(this.dialog);
			else await animateWithClass(this.dialog, "pulse");
		}
	}
	/**
	* Suspends the modal when third-party CSS (e.g. cookie banner blockers) hides an open dialog, so the page isn't
	* left scroll locked and inert. "open" stays true so the modal resumes if the dialog is rendered again.
	*/
	handleRenderedChange(isRendered) {
		if (!this.open) {
			this.renderedWatcher.stop();
			return;
		}
		if (!isRendered && this.dialog.open) {
			this.removeOpenListeners();
			this.dialog.close();
			unlockBodyScrolling(this);
		} else if (isRendered && !this.dialog.open) {
			this.addOpenListeners();
			this.dialog.showModal();
			lockBodyScrolling(this);
		}
	}
	handleOpenChange() {
		if (this.open && !this.dialog.open) this.show();
		else if (!this.open && this.dialog.open) {
			this.open = true;
			this.requestClose(this.dialog);
		} else if (!this.open) this.renderedWatcher.stop();
	}
	/** Shows the dialog. */
	async show() {
		const waShowEvent = new WaShowEvent();
		this.dispatchEvent(waShowEvent);
		if (waShowEvent.defaultPrevented) {
			this.open = false;
			return;
		}
		this.addOpenListeners();
		this.originalTrigger = document.activeElement;
		this.open = true;
		this.dialog.showModal();
		lockBodyScrolling(this);
		this.renderedWatcher.start(this.dialog);
		requestAnimationFrame(() => {
			const elementToFocus = this.querySelector("[autofocus]");
			if (elementToFocus && typeof elementToFocus.focus === "function") elementToFocus.focus();
			else this.dialog.focus();
		});
		await animateWithClass(this.dialog, "show");
		this.dispatchEvent(new WaAfterShowEvent());
	}
	render() {
		const hasHeader = !this.withoutHeader;
		const hasFooter = this.hasSlotController.test("footer", "withFooter");
		const hasLabel = this.label.length > 0 || this.hasSlotController.test("label", "withLabel");
		return b`
      <dialog
        part="dialog"
        aria-labelledby=${o$2(hasHeader && hasLabel ? "title" : void 0)}
        aria-label=${o$2(!hasHeader && this.label ? this.label : void 0)}
        class=${e$3({
			dialog: true,
			open: this.open
		})}
        @cancel=${this.handleDialogCancel}
        @click=${this.handleDialogClick}
        @pointerdown=${this.handleDialogPointerDown}
      >
        ${hasHeader ? b`
              <div part="header" class="header">
                <h2 part="title" class="title" id="title">
                  <!-- If there's no label, use an invisible character to prevent the header from collapsing -->
                  <slot name="label"> ${this.label.length > 0 ? this.label : String.fromCharCode(8203)} </slot>
                </h2>
                <div part="header-actions" class="header-actions">
                  <slot name="header-actions"></slot>
                  <wa-button
                    part="close-button"
                    exportparts="base:close-button__base, button:close-button__button"
                    class="close"
                    appearance="plain"
                    @click="${(event) => this.requestClose(event.target)}"
                  >
                    <wa-icon
                      name="xmark"
                      label=${this.localize.term("close")}
                      library="system"
                      variant="solid"
                    ></wa-icon>
                  </wa-button>
                </div>
              </div>
            ` : ""}

        <div part="body" class="body"><slot></slot></div>

        <!-- Use a hidden element so we still get "slotchange" events. -->
        <div part="footer" class="footer" ?hidden=${!hasFooter}>
          <slot name="footer"></slot>
        </div>
      </dialog>
    `;
	}
};
WaDialog.css = dialog_styles_default;
__decorateClass([e$5(".dialog")], WaDialog.prototype, "dialog", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaDialog.prototype, "open", 2);
__decorateClass([n$2({ reflect: true })], WaDialog.prototype, "label", 2);
__decorateClass([n$2({
	attribute: "without-header",
	type: Boolean,
	reflect: true
})], WaDialog.prototype, "withoutHeader", 2);
__decorateClass([n$2({
	attribute: "light-dismiss",
	type: Boolean
})], WaDialog.prototype, "lightDismiss", 2);
__decorateClass([n$2({
	attribute: "with-footer",
	type: Boolean
})], WaDialog.prototype, "withFooter", 2);
__decorateClass([n$2({
	attribute: "with-label",
	type: Boolean
})], WaDialog.prototype, "withLabel", 2);
__decorateClass([watch("open", { waitUntilFirstUpdate: true })], WaDialog.prototype, "handleOpenChange", 1);
WaDialog = __decorateClass([t$2("wa-dialog")], WaDialog);
document.addEventListener("click", (event) => {
	const dialogAttrEl = event.target.closest("[data-dialog]");
	if (dialogAttrEl instanceof Element) {
		const [command, id] = parseSpaceDelimitedTokens(dialogAttrEl.getAttribute("data-dialog") || "");
		if (command === "open" && id?.length) {
			const dialog = dialogAttrEl.getRootNode().getElementById(id);
			if (dialog?.localName === "wa-dialog") dialog.open = true;
			else console.warn(`A dialog with an ID of "${id}" could not be found in this document.`);
		}
	}
});
document.addEventListener("pointerdown", () => {});
// node_modules/@awesome.me/webawesome/dist/components/dialog/dialog.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.Q5SV6XNO.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var divider_styles_default = i$7`
  :host {
    --color: var(--wa-color-surface-border);
    --width: var(--wa-border-width-s);
    --spacing: var(--wa-space-m);
    --label-spacing: var(--wa-space-s);
    --label-offset: 0;
  }

  :host(:not([orientation='vertical'])) {
    display: block;
    border-top: solid var(--width) var(--color);
    margin: var(--spacing) 0;
  }

  :host([orientation='vertical']) {
    display: inline-block;
    height: 100%;
    border-inline-start: solid var(--width) var(--color);
    margin: 0 var(--spacing);
    min-block-size: 1lh;
  }

  /* With a label, the host's border gives way to two lines that flank the label */
  :host([with-label]) {
    align-items: center;
    gap: var(--label-spacing);
    border: none;
  }

  :host([with-label]:not([orientation='vertical'])) {
    display: flex;
  }

  :host([with-label][orientation='vertical']) {
    display: inline-flex;
    flex-direction: column;
  }

  :host([with-label])::before,
  :host([with-label])::after {
    content: '';
    flex: 1 1 0;
  }

  :host([with-label]:not([orientation='vertical']))::before,
  :host([with-label]:not([orientation='vertical']))::after {
    min-inline-size: 1em;
    border-top: solid var(--width) var(--color);
  }

  :host([with-label][orientation='vertical'])::before,
  :host([with-label][orientation='vertical'])::after {
    min-block-size: 1lh;
    border-inline-start: solid var(--width) var(--color);
  }

  :host([with-label][label-placement='start'])::before,
  :host([with-label][label-placement='end'])::after {
    flex: 0 0 var(--label-offset);
    min-inline-size: 0;
    min-block-size: 0;
  }

  :host(:not([with-label])) .label {
    display: none;
  }

  :host([with-label]) .label {
    display: inline-flex;
    align-items: center;
    gap: var(--wa-space-2xs);
    flex: 0 1 auto;
    color: var(--wa-color-text-quiet);
    font-size: var(--wa-font-size-s);
    line-height: var(--wa-line-height-condensed);
    text-align: center;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.RB4C7JY5.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaDivider = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.hasSlotController = new HasSlotController(this, "[default]");
		this.orientation = "horizontal";
		this.withLabel = false;
		this.labelPlacement = "center";
	}
	connectedCallback() {
		super.connectedCallback();
		this.setAttribute("role", "separator");
	}
	willUpdate(changedProperties) {
		this.withLabel = this.hasSlotController.test("[default]", "withLabel");
		super.willUpdate(changedProperties);
	}
	handleVerticalChange() {
		this.setAttribute("aria-orientation", this.orientation);
	}
	handleSlotChange() {
		if (this.internals) this.internals.ariaLabel = this.textContent?.trim() || null;
	}
	render() {
		return b`
      <div part="label" class="label">
        <slot @slotchange=${this.handleSlotChange}></slot>
      </div>
    `;
	}
};
WaDivider.css = divider_styles_default;
__decorateClass([n$2({ reflect: true })], WaDivider.prototype, "orientation", 2);
__decorateClass([n$2({
	attribute: "with-label",
	type: Boolean,
	reflect: true
})], WaDivider.prototype, "withLabel", 2);
__decorateClass([n$2({
	attribute: "label-placement",
	reflect: true
})], WaDivider.prototype, "labelPlacement", 2);
__decorateClass([watch("orientation")], WaDivider.prototype, "handleVerticalChange", 1);
WaDivider = __decorateClass([t$2("wa-divider")], WaDivider);
// node_modules/@awesome.me/webawesome/dist/components/divider/divider.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.JTOY5KP3.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaClearEvent = class extends Event {
	constructor() {
		super("wa-clear", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.MHRYUHI3.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function submitOnEnter(event, el) {
	const hasModifier = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
	if (event.key === "Enter" && !hasModifier) setTimeout(() => {
		if (!event.defaultPrevented && !event.isComposing) submitForm(el);
	});
}
var submittableTags = /* @__PURE__ */ new Map([
	["input", true],
	["wa-input", true],
	["wa-tag-input", true],
	["wa-number-input", true],
	["wa-otp-input", true],
	["wa-slider", true]
]);
var submittableTypes = /* @__PURE__ */ new Map([
	["button", false],
	["checkbox", false],
	["color", false],
	["date", false],
	["datetime-local", false],
	["email", true],
	["file", false],
	["hidden", false],
	["image", false],
	["month", false],
	["number", true],
	["password", true],
	["radio", false],
	["range", false],
	["reset", true],
	["search", true],
	["submit", false],
	["tel", true],
	["text", true],
	["time", false],
	["url", true],
	["week", false]
]);
var isSubmittableElement = (el) => {
	const tagName = el?.localName;
	if (!tagName) return false;
	if (!Boolean(submittableTags.get(tagName))) return false;
	if (tagName !== "input" && tagName !== "wa-input") return true;
	const type = el.type;
	return Boolean(submittableTypes.get(type));
};
function submitForm(el) {
	let form = null;
	if ("form" in el) form = el.form;
	if (!form && "getForm" in el) form = el.getForm();
	if (!form) return;
	const formElements = Array.from(form.elements);
	const button = formElements.find((el2) => el2.type === "submit");
	if (button) {
		if (button.matches(":disabled")) return;
		if (["input", "button"].includes(button.localName)) form.requestSubmit(button);
		else button.click();
		return;
	}
	if (formElements.filter(isSubmittableElement).length === 1) form.requestSubmit(null);
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.3ZKPD2O5.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var input_styles_default = i$7`
  :host {
    border-width: 0;
  }

  :host(:focus) {
    outline: none;
  }

  .text-field {
    display: flex;
    align-items: stretch;
    justify-content: start;
    position: relative;
    transition: inherit;
    height: var(--wa-form-control-height);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    cursor: text;
    color: var(--wa-form-control-value-color);
    font-size: var(--wa-form-control-value-font-size);
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    vertical-align: middle;
    width: 100%;
    transition:
      background-color var(--wa-transition-normal),
      border-color var(--wa-transition-normal),
      outline-color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    background-color: var(--wa-form-control-background-color);
    box-shadow: var(--box-shadow);
    padding: 0 var(--wa-form-control-padding-inline);
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    /* Only ring the field when the text input has focus, not inner buttons */
    &:has(input:focus, textarea:focus) {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled inputs */
    &:has(:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .text-field {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .text-field {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .text-field {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  :host([pill]) .text-field {
    border-radius: var(--wa-border-radius-pill) !important;
  }

  .text-field {
    /* Show autofill styles over the entire text field, not just the native <input> */
    &:has(:autofill),
    &:has(:-webkit-autofill) {
      background-color: var(--wa-color-brand-fill-quiet) !important;
    }

    input,
    textarea {
      /*
      Fixes an alignment issue with placeholders.
      https://github.com/shoelace-style/webawesome/issues/342
    */
      height: 100%;

      padding: 0;
      border: none;
      outline: none;
      box-shadow: none;
      margin: 0;
      cursor: inherit;
      -webkit-appearance: none;
      font: inherit;

      /* Turn off Safari's autofill styles */
      &:-webkit-autofill,
      &:-webkit-autofill:hover,
      &:-webkit-autofill:focus,
      &:-webkit-autofill:active {
        -webkit-background-clip: text;
        background-color: transparent;
        -webkit-text-fill-color: inherit;
      }
    }
  }

  input {
    flex: 1 1 auto;
    min-width: 0;
    height: 100%;
    transition: inherit;

    /* prettier-ignore */
    background-color: rgb(118 118 118 / 0); /* ensures proper placeholder styles in webkit's date input */
    height: calc(var(--wa-form-control-height) - var(--border-width) * 2);
    padding-block: 0;
    color: inherit;

    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }

    &::-webkit-search-decoration,
    &::-webkit-search-cancel-button,
    &::-webkit-search-results-button,
    &::-webkit-search-results-decoration {
      -webkit-appearance: none;
    }

    &:focus {
      outline: none;
    }
  }

  textarea {
    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }
  }

  .start,
  .end {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    cursor: default;

    &::slotted(wa-icon) {
      color: var(--wa-color-neutral-on-quiet);
    }
  }

  .start::slotted(*) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  .end::slotted(*) {
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  /*
   * Clearable + Password Toggle
   */

  .clear,
  .password-toggle {
    position: relative;
    display: inline-flex;
    align-self: center;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    height: 1.5em;
    font-size: inherit;
    color: var(--wa-color-neutral-on-quiet);
    border: none;
    border-radius: var(--wa-border-radius-s);
    background: none;
    padding: 0;
    transition: var(--wa-transition-normal) color;
    cursor: pointer;
    /* The box is wider than the glyph, so overhang half of that growth on each side. Keeps the
       glyph flush with the field's trailing padding edge, like every other form control. */
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - 0.125em);
    margin-inline-end: -0.125em;

    &::after {
      content: '';
      position: absolute;
      inset-inline: 0;
      height: var(--wa-form-control-height);
    }

    @media (hover: hover) {
      &:hover {
        color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
      }
    }

    &:active {
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
    }

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: var(--wa-focus-ring-offset);
    }
  }

  /* Don't show the browser's password toggle in Edge */
  ::-ms-reveal {
    display: none;
  }

  /* Hide the built-in number spinner */
  :host([without-spin-buttons]) input[type='number'] {
    -moz-appearance: textfield;

    &::-webkit-outer-spin-button,
    &::-webkit-inner-spin-button {
      -webkit-appearance: none;
      display: none;
    }
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.JPBXG7RE.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var form_control_styles_default = i$7`
  :host {
    display: flex;
    flex-direction: column;
  }

  /* Treat wrapped labels, inputs, and hints as direct children of the host element */
  [part~='form-control'] {
    display: contents;
  }

  /* Label */
  :is([part~='form-control-label'], [part~='label']):has(*:not(:empty)),
  :is([part~='form-control-label'], [part~='label']).has-label {
    display: inline-flex;
    color: var(--wa-form-control-label-color);
    font-weight: var(--wa-form-control-label-font-weight);
    line-height: var(--wa-form-control-label-line-height);
    margin-block-end: 0.5em;
  }

  :host([required]) :is([part~='form-control-label'], [part~='label'])::after {
    content: var(--wa-form-control-required-content);
    margin-inline-start: var(--wa-form-control-required-content-offset);
    color: var(--wa-form-control-required-content-color);
  }

  /* Help text */
  [part~='hint'] {
    display: block;
    color: var(--wa-form-control-hint-color);
    font-weight: var(--wa-form-control-hint-font-weight);
    line-height: var(--wa-form-control-hint-line-height);
    margin-block-start: 0.5em;
    font-size: var(--wa-font-size-smaller);

    &:not(.has-slotted, .has-hint, .has-count) {
      display: none;
    }
  }
`;
// node_modules/lit-html/directives/live.js
/**
* @license
* Copyright 2020 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var l = e$4(class extends i$3 {
	constructor(r) {
		if (super(r), r.type !== t$1.PROPERTY && r.type !== t$1.ATTRIBUTE && r.type !== t$1.BOOLEAN_ATTRIBUTE) throw Error("The `live` directive is not allowed on child or event bindings");
		if (!r$1(r)) throw Error("`live` bindings can only contain a single expression");
	}
	render(r) {
		return r;
	}
	update(i, [t]) {
		if (t === E || t === A) return t;
		const o = i.element, l = i.name;
		if (i.type === t$1.PROPERTY) {
			if (t === o[l]) return E;
		} else if (i.type === t$1.BOOLEAN_ATTRIBUTE) {
			if (!!t === o.hasAttribute(l)) return E;
		} else if (i.type === t$1.ATTRIBUTE && o.getAttribute(l) === t + "") return E;
		return p(i), t;
	}
});
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.UQFXQRWM.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaInput = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super(...arguments);
		this.assumeInteractionOn = ["blur", "input"];
		this.hasSlotController = new HasSlotController(this, "hint", "label");
		this.localize = new LocalizeController(this);
		this.title = "";
		this.type = "text";
		this._value = null;
		this.defaultValue = this.getAttribute("value") || null;
		this.size = "m";
		this.appearance = "outlined";
		this.pill = false;
		this.label = "";
		this.hint = "";
		this.withClear = false;
		this.placeholder = "";
		this.readonly = false;
		this.passwordToggle = false;
		this.passwordVisible = false;
		this.withoutSpinButtons = false;
		this.required = false;
		this.spellcheck = true;
		this.withLabel = false;
		this.withHint = false;
	}
	static get validators() {
		return [...super.validators, MirrorValidator()];
	}
	/** The current value of the input, submitted as a name/value pair with form data. */
	get value() {
		if (this.valueHasChanged) return this._value;
		return this._value ?? this.defaultValue;
	}
	set value(val) {
		if (this._value === val) return;
		this.valueHasChanged = true;
		this._value = val;
	}
	/**
	* @internal
	*/
	updateFormValue(value) {
		if (value == null) {
			this.setValue("", null);
			return;
		}
		super.updateFormValue(value);
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	handleChange(event) {
		this.value = this.input.value;
		this.relayNativeEvent(event, {
			bubbles: true,
			composed: true
		});
	}
	handleClearClick(event) {
		event.preventDefault();
		if (this.value !== "") {
			this.value = "";
			this.updateComplete.then(() => {
				this.dispatchEvent(new WaClearEvent());
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
			});
		}
		this.input.focus();
	}
	handleInput() {
		this.value = this.input.value;
	}
	handleKeyDown(event) {
		submitOnEnter(event, this);
	}
	handlePasswordToggle() {
		this.passwordVisible = !this.passwordVisible;
	}
	updated(changedProperties) {
		super.updated(changedProperties);
		if (changedProperties.has("value") || changedProperties.has("defaultValue") || changedProperties.has("type")) {
			if (this.input && [
				"number",
				"date",
				"time",
				"datetime-local"
			].includes(this.type) && this.value && this.input.value !== this.value) this._value = this.input.value;
			this.customStates.set("blank", !this.value);
			this.updateValidity();
		}
		if (!(changedProperties.size === 1 && changedProperties.has("validity"))) this.updateValidity();
	}
	handleStepChange() {
		this.input.step = String(this.step);
		this.updateValidity();
	}
	/** Sets focus on the input. */
	focus(options) {
		this.input.focus(options);
	}
	/** Removes focus from the input. */
	blur() {
		this.input.blur();
	}
	/** Selects all the text in the input. */
	select() {
		this.input.select();
	}
	/** Sets the start and end positions of the text selection (0-based). */
	setSelectionRange(selectionStart, selectionEnd, selectionDirection = "none") {
		this.input.setSelectionRange(selectionStart, selectionEnd, selectionDirection);
	}
	/** Replaces a range of text with a new string. */
	setRangeText(replacement, start, end, selectMode = "preserve") {
		const selectionStart = start ?? this.input.selectionStart;
		const selectionEnd = end ?? this.input.selectionEnd;
		this.input.setRangeText(replacement, selectionStart, selectionEnd, selectMode);
		if (this.value !== this.input.value) this.value = this.input.value;
	}
	/** Displays the browser picker for an input element (only works if the browser supports it for the input type). */
	showPicker() {
		if ("showPicker" in HTMLInputElement.prototype) this.input.showPicker();
	}
	/** Increments the value of a numeric input type by the value of the step attribute. */
	stepUp() {
		this.input.stepUp();
		if (this.value !== this.input.value) this.value = this.input.value;
	}
	/** Decrements the value of a numeric input type by the value of the step attribute. */
	stepDown() {
		this.input.stepDown();
		if (this.value !== this.input.value) this.value = this.input.value;
	}
	formResetCallback() {
		this.value = null;
		if (this.input) this.input.value = this.value;
		super.formResetCallback();
	}
	render() {
		const hasLabelSlot = this.hasSlotController.test("label", "withLabel");
		const hasHintSlot = this.hasSlotController.test("hint", "withHint");
		const hasLabel = this.label ? true : !!hasLabelSlot;
		const hasHint = this.hint ? true : !!hasHintSlot;
		const hasClearIcon = this.withClear && !this.disabled && !this.readonly;
		const isClearIconVisible = (!this.didSSR || this.hasUpdated) && hasClearIcon && (typeof this.value === "number" || this.value && this.value.length > 0);
		return b`
      <label
        part="form-control-label label"
        class=${e$3({
			label: true,
			"has-label": hasLabel
		})}
        for="input"
        aria-hidden=${hasLabel ? "false" : "true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base input-wrapper" class="text-field">
        <slot name="start" part="start" class="start"></slot>

        <input
          part="input"
          id="input"
          class="control"
          type=${this.type === "password" && this.passwordVisible ? "text" : this.type}
          title=${this.title}
          name=${o$2(this.name)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${o$2(this.placeholder)}
          minlength=${o$2(this.minlength)}
          maxlength=${o$2(this.maxlength)}
          min=${o$2(this.min)}
          max=${o$2(this.max)}
          step=${o$2(this.step)}
          .value=${l(this.value ?? "")}
          autocapitalize=${o$2(this.autocapitalize)}
          autocomplete=${o$2(this.autocomplete)}
          autocorrect=${this.autocorrect ? "on" : "off"}
          ?autofocus=${this.autofocus}
          spellcheck=${this.spellcheck}
          pattern=${o$2(this.pattern)}
          enterkeyhint=${o$2(this.enterkeyhint)}
          inputmode=${o$2(this.inputmode)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
        />

        ${isClearIconVisible ? b`
              <button
                part="clear-button"
                class="clear"
                type="button"
                aria-label=${this.localize.term("clearEntry")}
                @click=${this.handleClearClick}
                tabindex="-1"
              >
                <slot name="clear-icon">
                  <wa-icon name="circle-xmark" library="system" variant="regular"></wa-icon>
                </slot>
              </button>
            ` : ""}
        ${this.passwordToggle && !this.disabled ? b`
              <button
                part="password-toggle-button"
                class="password-toggle"
                type="button"
                aria-label=${this.localize.term(this.passwordVisible ? "hidePassword" : "showPassword")}
                @click=${this.handlePasswordToggle}
              >
                ${!this.passwordVisible ? b`
                      <slot name="show-password-icon">
                        <wa-icon name="eye" library="system" variant="regular"></wa-icon>
                      </slot>
                    ` : b`
                      <slot name="hide-password-icon">
                        <wa-icon name="eye-slash" library="system" variant="regular"></wa-icon>
                      </slot>
                    `}
              </button>
            ` : ""}

        <slot name="end" part="end" class="end"></slot>
      </div>

      <slot
        id="hint"
        part="hint"
        name="hint"
        class=${e$3({ "has-slotted": hasHint })}
        aria-hidden=${hasHint ? "false" : "true"}
        >${this.hint}</slot
      >
    `;
	}
};
WaInput.css = [
	size_styles_default,
	form_control_styles_default,
	input_styles_default
];
WaInput.shadowRootOptions = {
	...WebAwesomeFormAssociatedElement.shadowRootOptions,
	delegatesFocus: true
};
__decorateClass([e$5("input")], WaInput.prototype, "input", 2);
__decorateClass([n$2()], WaInput.prototype, "title", 2);
__decorateClass([n$2({ reflect: true })], WaInput.prototype, "type", 2);
__decorateClass([r$2()], WaInput.prototype, "value", 1);
__decorateClass([n$2({
	attribute: "value",
	reflect: true
})], WaInput.prototype, "defaultValue", 2);
__decorateClass([n$2({ reflect: true })], WaInput.prototype, "size", 2);
__decorateClass([watch("size")], WaInput.prototype, "handleSizeChange", 1);
__decorateClass([n$2({ reflect: true })], WaInput.prototype, "appearance", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaInput.prototype, "pill", 2);
__decorateClass([n$2()], WaInput.prototype, "label", 2);
__decorateClass([n$2({ attribute: "hint" })], WaInput.prototype, "hint", 2);
__decorateClass([n$2({
	attribute: "with-clear",
	type: Boolean
})], WaInput.prototype, "withClear", 2);
__decorateClass([n$2()], WaInput.prototype, "placeholder", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaInput.prototype, "readonly", 2);
__decorateClass([n$2({
	attribute: "password-toggle",
	type: Boolean
})], WaInput.prototype, "passwordToggle", 2);
__decorateClass([n$2({
	attribute: "password-visible",
	type: Boolean
})], WaInput.prototype, "passwordVisible", 2);
__decorateClass([n$2({
	attribute: "without-spin-buttons",
	type: Boolean,
	reflect: true
})], WaInput.prototype, "withoutSpinButtons", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaInput.prototype, "required", 2);
__decorateClass([n$2()], WaInput.prototype, "pattern", 2);
__decorateClass([n$2({ type: Number })], WaInput.prototype, "minlength", 2);
__decorateClass([n$2({ type: Number })], WaInput.prototype, "maxlength", 2);
__decorateClass([n$2()], WaInput.prototype, "min", 2);
__decorateClass([n$2()], WaInput.prototype, "max", 2);
__decorateClass([n$2()], WaInput.prototype, "step", 2);
__decorateClass([n$2()], WaInput.prototype, "autocapitalize", 2);
__decorateClass([n$2({
	type: Boolean,
	converter: {
		fromAttribute: (value) => !value || value === "off" ? false : true,
		toAttribute: (value) => value ? "on" : "off"
	}
})], WaInput.prototype, "autocorrect", 2);
__decorateClass([n$2()], WaInput.prototype, "autocomplete", 2);
__decorateClass([n$2({ type: Boolean })], WaInput.prototype, "autofocus", 2);
__decorateClass([n$2()], WaInput.prototype, "enterkeyhint", 2);
__decorateClass([n$2({
	type: Boolean,
	converter: {
		fromAttribute: (value) => !value || value === "false" ? false : true,
		toAttribute: (value) => value ? "true" : "false"
	}
})], WaInput.prototype, "spellcheck", 2);
__decorateClass([n$2()], WaInput.prototype, "inputmode", 2);
__decorateClass([n$2({
	attribute: "with-label",
	type: Boolean
})], WaInput.prototype, "withLabel", 2);
__decorateClass([n$2({
	attribute: "with-hint",
	type: Boolean
})], WaInput.prototype, "withHint", 2);
__decorateClass([watch("step", { waitUntilFirstUpdate: true })], WaInput.prototype, "handleStepChange", 1);
WaInput = __decorateClass([t$2("wa-input")], WaInput);
WaInput.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/components/input/input.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.C3KOHXUM.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var option_styles_default = i$7`
  :host {
    --current-text-color: var(--wa-color-brand-on-loud);

    display: block;
    color: var(--wa-color-text-normal);
    -webkit-user-select: none;
    user-select: none;

    position: relative;
    display: flex;
    align-items: center;
    font: inherit;
    padding: 0.5em 1em 0.5em 0.25em;
    border-radius: var(--wa-border-radius-s);
    line-height: var(--wa-line-height-condensed);
    transition: var(--wa-transition-fast) background-color var(--wa-transition-easing);
    cursor: pointer;
  }

  :host(:focus) {
    outline: none;
  }

  @media (hover: hover) {
    :host(:not(:state(disabled), :state(current)):is(:state(hover), :hover)) {
      background-color: var(--wa-color-neutral-fill-normal);
      color: var(--wa-color-neutral-on-normal);
    }
  }

  :host(:state(current)),
  :host(:state(disabled):state(current)) {
    background-color: var(--wa-form-control-activated-color);
    color: var(--current-text-color);
    opacity: 1;
  }

  :host(:state(disabled)) {
    outline: none;
    opacity: 0.5;
    cursor: not-allowed;
  }

  .label {
    flex: 1 1 auto;
    display: inline-block;
  }

  .check {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--wa-font-size-smaller);
    visibility: hidden;
    width: 2em;
  }

  :host(:state(selected)) .check {
    visibility: visible;
  }

  .start,
  .end {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
  }

  .start::slotted(*) {
    margin-inline-end: 0.5em;
  }

  .end::slotted(*) {
    margin-inline-start: 0.5em;
  }

  @media (forced-colors: active) {
    :host(:hover:not([aria-disabled='true'])) {
      outline: dashed 1px SelectedItem;
      outline-offset: -1px;
    }
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.Q4VQU45W.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function getText(root, depth = 0) {
	if (!root || !globalThis.Node) return "";
	if (typeof root[Symbol.iterator] === "function") return (Array.isArray(root) ? root : [...root]).map((node2) => getText(node2, --depth)).join("");
	let node = root;
	if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
	if (node.nodeType === Node.ELEMENT_NODE) {
		let element = node;
		if (element.hasAttribute("slot") || element.matches("style, script")) return "";
		if (element instanceof HTMLSlotElement) {
			let assignedNodes = element.assignedNodes({ flatten: true });
			if (assignedNodes.length > 0) return getText(assignedNodes, --depth);
		}
		return depth > -1 ? getText(element, --depth) : element.textContent ?? "";
	}
	return node.hasChildNodes() ? getText(node.childNodes, --depth) : "";
}
var WaOption = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
		this.cachedDefaultLabel = "";
		this.isInitialized = false;
		this.isDefaultLabelDirty = true;
		this.current = false;
		this.value = "";
		this.disabled = false;
		this.selected = false;
		this.defaultSelected = false;
		this._label = "";
		this.handleHover = (event) => {
			if (event.type === "mouseenter") this.customStates.set("hover", true);
			else if (event.type === "mouseleave") this.customStates.set("hover", false);
		};
	}
	set label(value) {
		const oldValue = this._label;
		this._label = value || "";
		if (this._label !== oldValue) this.requestUpdate("label", oldValue);
	}
	get label() {
		if (this._label) return this._label;
		return this.defaultLabel;
	}
	/** The default label, generated from the element contents. Will be equal to `label` in most cases. */
	get defaultLabel() {
		if (this.isDefaultLabelDirty || !this.cachedDefaultLabel) this.updateDefaultLabel();
		return this.cachedDefaultLabel;
	}
	connectedCallback() {
		super.connectedCallback();
		this.setAttribute("role", "option");
		this.setAttribute("aria-selected", "false");
		this.addEventListener("mouseenter", this.handleHover);
		this.addEventListener("mouseleave", this.handleHover);
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		this.removeEventListener("mouseenter", this.handleHover);
		this.removeEventListener("mouseleave", this.handleHover);
	}
	handleDefaultSlotChange() {
		this.isDefaultLabelDirty = true;
		if (!this.isInitialized) {
			this.isInitialized = true;
			return;
		}
		const controller = this.closest("wa-select, wa-combobox");
		if (controller) customElements.whenDefined(controller.localName).then(() => controller.handleDefaultSlotChange?.());
	}
	willUpdate(changedProperties) {
		if (changedProperties.has("defaultSelected")) {
			if (this.didSSR && this.hasUpdated || !this.didSSR) this.syncDefaultSelected();
		}
		super.willUpdate(changedProperties);
	}
	syncDefaultSelected() {
		if ("closest" in this) {
			if (!this.closest("wa-combobox, wa-select")?.hasInteracted) {
				if (this.defaultSelected) {
					const oldVal = this.selected;
					this.selected = this.defaultSelected;
					this.requestUpdate("selected", oldVal);
				}
			}
		}
	}
	updated(changedProperties) {
		if (changedProperties.has("disabled")) {
			this.setAttribute("aria-disabled", this.disabled ? "true" : "false");
			this.customStates.set("disabled", this.disabled);
		}
		if (changedProperties.has("selected")) {
			this.setAttribute("aria-selected", this.selected ? "true" : "false");
			this.customStates.set("selected", this.selected);
		}
		if (changedProperties.has("value")) {
			if (typeof this.value !== "string") this.value = String(this.value);
			this.handleDefaultSlotChange();
		}
		if (changedProperties.has("current")) this.customStates.set("current", this.current);
		super.updated(changedProperties);
	}
	async firstUpdated(changedProperties) {
		super.firstUpdated(changedProperties);
		if (this.didSSR && !this.hasUpdated) {
			await this.updateComplete;
			this.syncDefaultSelected();
		} else this.syncDefaultSelected();
		if (this.selected && !this.defaultSelected) {
			const parent = this.closest("wa-select, wa-combobox");
			if (parent && !parent.hasInteracted) {
				await customElements.whenDefined(parent?.localName);
				await parent.updateComplete;
				parent.selectionChanged?.();
			}
		}
	}
	updateDefaultLabel() {
		let oldValue = this.cachedDefaultLabel;
		this.cachedDefaultLabel = getText(this).trim();
		this.isDefaultLabelDirty = false;
		let changed = this.cachedDefaultLabel !== oldValue;
		if (!this._label && changed) this.requestUpdate("label", oldValue);
		return changed;
	}
	render() {
		let selected = this.selected;
		if (this.didSSR && !this.hasUpdated) {
			this.updateComplete.then(() => {
				this.requestUpdate();
			});
			return A;
		}
		return b`
      ${selected ? b`<wa-icon
            part="checked-icon"
            class="check"
            name="check"
            library="system"
            variant="solid"
            aria-hidden="true"
          ></wa-icon>` : b`<span part="checked-icon" class="check" aria-hidden="true"></span>`}
      <slot part="start" name="start" class="start"></slot>
      <slot part="label" class="label" @slotchange=${this.handleDefaultSlotChange}></slot>
      <slot part="end" name="end" class="end"></slot>
    `;
	}
};
WaOption.css = option_styles_default;
__decorateClass([e$5(".label")], WaOption.prototype, "defaultSlot", 2);
__decorateClass([r$2()], WaOption.prototype, "current", 2);
__decorateClass([n$2({ reflect: true })], WaOption.prototype, "value", 2);
__decorateClass([n$2({ type: Boolean })], WaOption.prototype, "disabled", 2);
__decorateClass([n$2({
	type: Boolean,
	attribute: false
})], WaOption.prototype, "selected", 2);
__decorateClass([n$2({
	type: Boolean,
	attribute: "selected"
})], WaOption.prototype, "defaultSelected", 2);
__decorateClass([n$2()], WaOption.prototype, "label", 1);
WaOption = __decorateClass([t$2("wa-option")], WaOption);
// node_modules/@awesome.me/webawesome/dist/components/option/option.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.VTVNMJUY.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var progress_bar_styles_default = i$7`
  :host {
    --track-height: 1rem;
    --track-color: var(--wa-color-neutral-fill-normal);
    --indicator-color: var(--wa-color-brand-fill-loud);

    display: flex;
  }

  .progress-bar {
    flex: 1 1 auto;
    display: flex;
    position: relative;
    overflow: hidden;
    height: var(--track-height);
    border-radius: var(--wa-border-radius-pill);
    background-color: var(--track-color);
    color: var(--wa-color-brand-on-loud);
    font-size: var(--wa-font-size-s);
  }

  .indicator {
    width: var(--percentage);
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--indicator-color);
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    line-height: 1;
    font-weight: var(--wa-font-weight-semibold);
    transition: all var(--wa-transition-slow, 200ms) var(--wa-transition-easing, ease);
    user-select: none;
    -webkit-user-select: none;
  }

  /* Indeterminate */
  :host([indeterminate]) .indicator {
    position: absolute;
    inset-block: 0;
    inline-size: 50%;
    animation: wa-progress-indeterminate 2.5s infinite cubic-bezier(0.37, 0, 0.63, 1);
  }

  @media (forced-colors: active) {
    .progress-bar {
      outline: solid 1px SelectedItem;
      background-color: var(--wa-color-surface-default);
    }

    .indicator {
      outline: solid 1px SelectedItem;
      background-color: SelectedItem;
    }
  }

  @keyframes wa-progress-indeterminate {
    0% {
      inset-inline-start: -50%;
    }

    75%,
    100% {
      inset-inline-start: 100%;
    }
  }
`;
// node_modules/@awesome.me/webawesome/node_modules/nanoid/url-alphabet/index.js
var urlAlphabet = "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict";
// node_modules/@awesome.me/webawesome/node_modules/nanoid/index.browser.js
var nanoid = (size = 21) => {
	let id = "";
	let bytes = crypto.getRandomValues(new Uint8Array(size |= 0));
	while (size--) id += urlAlphabet[bytes[size] & 63];
	return id;
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.KNJT7KBU.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function clamp$1(value, min, max) {
	const noNegativeZero = (n) => Object.is(n, -0) ? 0 : n;
	if (value < min) return noNegativeZero(min);
	if (value > max) return noNegativeZero(max);
	return noNegativeZero(value);
}
function uniqueId(prefix = "") {
	return `${prefix}${nanoid()}`;
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.ENOWCCK2.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaProgressBar = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
		this.value = 0;
		this.indeterminate = false;
		this.label = "";
	}
	willUpdate(changedProperties) {
		if (this.style == null) this.setStyleProperty("--percentage", `${clamp$1(this.value, 0, 100)}%`);
		super.willUpdate(changedProperties);
	}
	updated(changedProperties) {
		if (changedProperties.has("value")) requestAnimationFrame(() => {
			this.style.setProperty("--percentage", `${clamp$1(this.value, 0, 100)}%`);
		});
		super.updated(changedProperties);
	}
	render() {
		return b`
      <div
        part="base progress-bar"
        class="progress-bar"
        role="progressbar"
        title=${o$2(this.title)}
        aria-label=${this.label.length > 0 ? this.label : this.localize.term("progress")}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${this.indeterminate ? "0" : this.value}
      >
        <div part="indicator" class="indicator">
          ${!this.indeterminate ? b` <slot part="label" class="label"></slot> ` : ""}
        </div>
      </div>
    `;
	}
};
WaProgressBar.css = progress_bar_styles_default;
__decorateClass([n$2({
	type: Number,
	reflect: true
})], WaProgressBar.prototype, "value", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaProgressBar.prototype, "indeterminate", 2);
__decorateClass([n$2()], WaProgressBar.prototype, "label", 2);
WaProgressBar = __decorateClass([t$2("wa-progress-bar")], WaProgressBar);
// node_modules/@awesome.me/webawesome/dist/components/progress-bar/progress-bar.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.BELHQIBT.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var radio_styles_default = i$7`
  :host {
    --checked-icon-color: var(--wa-form-control-activated-color);
    --checked-icon-scale: 0.7;

    color: var(--wa-form-control-value-color);
    display: inline-flex;
    flex-direction: row;
    align-items: top;
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  :host(:focus) {
    outline: none;
  }

  /* When the control isn't checked, hide the circle for Windows High Contrast mode a11y */
  :host(:not(:state(checked))) svg circle {
    opacity: 0;
  }

  [part~='label'] {
    display: inline;
  }

  [part~='hint'] {
    margin-block-start: 0.5em;
  }

  /* Default spacing for default appearance radios */
  :host([appearance='default']) {
    margin-block: 0.375em; /* Half of the original 0.75em gap on each side */
  }

  :host([appearance='default'][data-wa-radio-horizontal]) {
    margin-block: 0;
    margin-inline: 0.5em; /* Half of the original 1em gap on each side */
  }

  /* Remove margin from first/last items to prevent extra space */
  :host([appearance='default'][data-wa-radio-first]) {
    margin-block-start: 0;
    margin-inline-start: 0;
  }

  :host([appearance='default'][data-wa-radio-last]) {
    margin-block-end: 0;
    margin-inline-end: 0;
  }

  /* Button appearance have no spacing, they get handled by the overlap margins below */
  :host([appearance='button']) {
    margin: 0;
    align-items: center;
    min-height: var(--wa-form-control-height);
    background-color: var(--wa-color-surface-default);
    border: var(--wa-form-control-border-width) var(--wa-form-control-border-style) var(--wa-form-control-border-color);
    border-radius: var(--wa-border-radius-m);
    padding: 0 var(--wa-form-control-padding-inline);
    transition:
      background-color var(--wa-transition-fast),
      border-color var(--wa-transition-fast);
  }

  /* Default appearance */
  :host([appearance='default']) {
    .control {
      flex: 0 0 auto;
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: var(--wa-form-control-toggle-size);
      height: var(--wa-form-control-toggle-size);
      border-color: var(--wa-form-control-border-color);
      border-radius: 50%;
      border-style: var(--wa-form-control-border-style);
      border-width: var(--wa-form-control-border-width);
      background-color: var(--wa-form-control-background-color);
      color: transparent;
      transition:
        background var(--wa-transition-normal),
        border-color var(--wa-transition-fast),
        box-shadow var(--wa-transition-fast),
        color var(--wa-transition-fast);
      transition-timing-function: var(--wa-transition-easing);

      margin-inline-end: 0.5em;
    }

    .checked-icon {
      display: flex;
      fill: currentColor;
      width: var(--wa-form-control-toggle-size);
      height: var(--wa-form-control-toggle-size);
      scale: var(--checked-icon-scale);
    }
  }

  /* Button appearance */
  :host([appearance='button']) {
    .control {
      display: none;
    }
  }

  /* Checked */
  :host(:state(checked)) .control {
    color: var(--checked-icon-color);
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-form-control-background-color);
  }

  /* Focus */
  :host(:focus-visible) .control {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled */
  :host(:state(disabled)) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Horizontal grouping - remove inner border radius */
  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-inner]) {
    border-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-first]) {
    border-start-end-radius: 0;
    border-end-end-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-last]) {
    border-start-start-radius: 0;
    border-end-start-radius: 0;
  }

  /* Vertical grouping - remove inner border radius */
  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-inner]) {
    border-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-first]) {
    border-end-start-radius: 0;
    border-end-end-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-last]) {
    border-start-start-radius: 0;
    border-start-end-radius: 0;
  }

  @media (hover: hover) {
    :host([appearance='button']:hover:not(:state(disabled), :state(checked))) {
      background-color: color-mix(in srgb, var(--wa-color-surface-default) 95%, var(--wa-color-mix-hover));
    }
  }

  :host([appearance='button']:focus-visible) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  :host([appearance='button']:state(checked)) {
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-color-brand-fill-quiet);
  }

  :host([appearance='button']:state(checked):focus-visible) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Button overlap margins */
  :host([appearance='button'][data-wa-radio-horizontal]:not([data-wa-radio-first])) {
    margin-inline-start: calc(-1 * var(--wa-form-control-border-width));
  }

  :host([appearance='button'][data-wa-radio-vertical]:not([data-wa-radio-first])) {
    margin-block-start: calc(-1 * var(--wa-form-control-border-width));
  }

  /* Ensure interactive states are visible above adjacent buttons */
  :host([appearance='button']:hover),
  :host([appearance='button']:state(checked)) {
    position: relative;
    z-index: 1;
  }

  :host([appearance='button']:focus-visible) {
    z-index: 2;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.7PO7HNMU.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaRadio = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super();
		this.checked = false;
		this.forceDisabled = false;
		this.appearance = "default";
		this.disabled = false;
		this.handleClick = () => {
			if (!this.disabled && !this.forceDisabled) this.checked = true;
		};
		this.addEventListener("click", this.handleClick);
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	connectedCallback() {
		super.connectedCallback();
		this.setInitialAttributes();
	}
	setInitialAttributes() {
		this.setAttribute("role", "radio");
		this.tabIndex = 0;
		this.setAttribute("aria-disabled", this.disabled || this.forceDisabled ? "true" : "false");
	}
	updated(changedProperties) {
		super.updated(changedProperties);
		if (changedProperties.has("checked")) {
			this.customStates.set("checked", this.checked);
			this.setAttribute("aria-checked", this.checked ? "true" : "false");
			if (!this.disabled && !this.forceDisabled) this.tabIndex = this.checked ? 0 : -1;
		}
		if (changedProperties.has("disabled") || changedProperties.has("forceDisabled")) {
			const effectivelyDisabled = this.disabled || this.forceDisabled;
			this.customStates.set("disabled", effectivelyDisabled);
			this.setAttribute("aria-disabled", effectivelyDisabled ? "true" : "false");
			if (effectivelyDisabled) this.tabIndex = -1;
			else this.tabIndex = this.checked ? 0 : -1;
		}
	}
	/**
	* @override
	*/
	setValue() {}
	render() {
		return b`
      <span part="control" class="control">
        ${this.checked ? b`
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" part="checked-icon" class="checked-icon">
                <circle cx="8" cy="8" r="8" />
              </svg>
            ` : ""}
      </span>

      <slot part="label" class="label"></slot>
    `;
	}
};
WaRadio.css = [
	form_control_styles_default,
	size_styles_default,
	radio_styles_default
];
__decorateClass([r$2()], WaRadio.prototype, "checked", 2);
__decorateClass([r$2()], WaRadio.prototype, "forceDisabled", 2);
__decorateClass([n$2({ reflect: true })], WaRadio.prototype, "value", 2);
__decorateClass([n$2({ reflect: true })], WaRadio.prototype, "appearance", 2);
__decorateClass([n$2({ reflect: true })], WaRadio.prototype, "size", 2);
__decorateClass([watch("size")], WaRadio.prototype, "handleSizeChange", 1);
__decorateClass([n$2({ type: Boolean })], WaRadio.prototype, "disabled", 2);
WaRadio = __decorateClass([t$2("wa-radio")], WaRadio);
WaRadio.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/components/radio/radio.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.GBDIGVZM.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var radio_group_styles_default = i$7`
  .form-control {
    position: relative;
    border: none;
    padding: 0;
    margin: 0;
  }

  .label {
    padding: 0;
  }

  .radio-group-required .label::after {
    content: var(--wa-form-control-required-content);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }

  [part~='form-control-input'] {
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    gap: 0; /* Radios handle their own spacing */
  }

  /* Horizontal */
  :host([orientation='horizontal']) [part~='form-control-input'] {
    flex-direction: row;
  }

  /* Help text */
  [part~='hint'] {
    margin-block-start: 0.5em;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.GWSUX3V5.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var RequiredValidator = (options = {}) => {
	let { validationElement, validationProperty } = options;
	if (!validationElement) {
		if (typeof document !== "undefined" && "createElement" in document) validationElement = Object.assign(document.createElement("input"), { required: true });
	}
	if (!validationProperty) validationProperty = "value";
	const obj = {
		observedAttributes: ["required"],
		message: validationElement?.validationMessage,
		checkValidity(element) {
			const validity = {
				message: "",
				isValid: true,
				invalidKeys: []
			};
			if (!(element.required ?? element.hasAttribute("required"))) return validity;
			if (!element[validationProperty]) {
				validity.message = typeof obj.message === "function" ? obj.message(element) : obj.message || "";
				validity.isValid = false;
				validity.invalidKeys.push("valueMissing");
			}
			return validity;
		}
	};
	return obj;
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.G4XPRTJE.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaRadioGroup = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super();
		this.hasSlotController = new HasSlotController(this, "hint", "label");
		this.label = "";
		this.hint = "";
		this.name = null;
		this.disabled = false;
		this.orientation = "vertical";
		this._value = null;
		this.defaultValue = this.getAttribute("value") || null;
		this.required = false;
		this.withLabel = false;
		this.withHint = false;
		this.handleRadioClick = (e) => {
			const clickedRadio = e.target.closest("wa-radio");
			if (!clickedRadio || clickedRadio.disabled || clickedRadio.forceDisabled || this.disabled) return;
			const oldValue = this.value;
			this.value = clickedRadio.value;
			clickedRadio.checked = true;
			const radios = this.getAllRadios();
			for (const radio of radios) {
				if (clickedRadio === radio) continue;
				radio.checked = false;
				radio.setAttribute("tabindex", "-1");
			}
			if (this.value !== oldValue) this.updateComplete.then(() => {
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
			});
		};
		this.addEventListener("keydown", this.handleKeyDown);
		this.addEventListener("click", this.handleRadioClick);
	}
	static get validators() {
		const validators = [RequiredValidator({ validationElement: Object.assign(document.createElement("input"), {
			required: true,
			type: "radio",
			name: uniqueId("__wa-radio")
		}) })];
		return [...super.validators, ...validators];
	}
	get value() {
		if (this.valueHasChanged) return this._value;
		return this._value ?? this.defaultValue;
	}
	set value(val) {
		if (typeof val === "number") val = String(val);
		this.valueHasChanged = true;
		this._value = val;
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	/**
	* We use the first available radio as the validationTarget similar to native HTML that shows the validation popup on
	* the first radio element.
	*/
	get validationTarget() {
		const radio = this.querySelector(":is(wa-radio):not([disabled])");
		if (!radio) return void 0;
		return radio;
	}
	updated(changedProperties) {
		if (changedProperties.has("disabled") || changedProperties.has("size") || changedProperties.has("value") || changedProperties.has("defaultValue")) this.syncRadioElements();
	}
	formResetCallback(...args) {
		this._value = null;
		super.formResetCallback(...args);
		this.syncRadioElements();
	}
	getAllRadios() {
		return [...this.querySelectorAll("wa-radio")];
	}
	handleLabelClick() {
		this.focus();
	}
	async syncRadioElements() {
		const radios = this.getAllRadios();
		radios.forEach((radio, index) => {
			if (this.size) radio.setAttribute("size", this.size);
			radio.toggleAttribute("data-wa-radio-horizontal", this.orientation !== "vertical");
			radio.toggleAttribute("data-wa-radio-vertical", this.orientation === "vertical");
			radio.toggleAttribute("data-wa-radio-first", index === 0);
			radio.toggleAttribute("data-wa-radio-inner", index !== 0 && index !== radios.length - 1);
			radio.toggleAttribute("data-wa-radio-last", index === radios.length - 1);
			radio.forceDisabled = this.disabled;
		});
		await Promise.all(radios.map(async (radio) => {
			await radio.updateComplete;
			if (radio.value === this.value) radio.checked = true;
			else radio.checked = false;
		}));
		if (this.disabled) radios.forEach((radio) => {
			radio.tabIndex = -1;
		});
		else {
			const enabledRadios = radios.filter((radio) => !radio.disabled);
			const checkedRadio = enabledRadios.find((radio) => radio.checked);
			if (enabledRadios.length > 0) {
				if (checkedRadio) enabledRadios.forEach((radio) => {
					radio.tabIndex = radio.checked ? 0 : -1;
				});
				else enabledRadios.forEach((radio, index) => {
					radio.tabIndex = index === 0 ? 0 : -1;
				});
			}
			radios.filter((radio) => radio.disabled).forEach((radio) => {
				radio.tabIndex = -1;
			});
		}
	}
	handleKeyDown(event) {
		if (![
			"ArrowUp",
			"ArrowDown",
			"ArrowLeft",
			"ArrowRight",
			" "
		].includes(event.key) || this.disabled) return;
		const radios = this.getAllRadios().filter((radio) => !radio.disabled);
		if (radios.length <= 0) return;
		event.preventDefault();
		const oldValue = this.value;
		const checkedRadio = radios.find((radio) => radio.checked) ?? radios[0];
		const incr = event.key === " " ? 0 : ["ArrowUp", "ArrowLeft"].includes(event.key) ? -1 : 1;
		let index = radios.indexOf(checkedRadio) + incr;
		if (!index) index = 0;
		if (index < 0) index = radios.length - 1;
		if (index > radios.length - 1) index = 0;
		const hasRadioButtons = radios.some((radio) => radio.tagName.toLowerCase() === "wa-radio-button");
		this.getAllRadios().forEach((radio) => {
			radio.checked = false;
			if (!hasRadioButtons) radio.setAttribute("tabindex", "-1");
		});
		this.value = radios[index].value;
		radios[index].checked = true;
		if (!hasRadioButtons) {
			radios[index].setAttribute("tabindex", "0");
			radios[index].focus();
		} else radios[index].shadowRoot.querySelector("button").focus();
		if (this.value !== oldValue) this.updateComplete.then(() => {
			this.dispatchEvent(new InputEvent("input", {
				bubbles: true,
				composed: true
			}));
			this.dispatchEvent(new Event("change", {
				bubbles: true,
				composed: true
			}));
		});
		event.preventDefault();
	}
	/** Sets focus on the radio group. */
	focus(options) {
		if (this.disabled) return;
		const radios = this.getAllRadios();
		const checked = radios.find((radio) => radio.checked && !radio.disabled);
		const firstEnabledRadio = radios.find((radio) => !radio.disabled);
		const radioToFocus = checked || firstEnabledRadio;
		if (radioToFocus) radioToFocus.focus(options);
	}
	render() {
		const hasLabelSlot = this.hasSlotController.test("label", "withLabel");
		const hasHintSlot = this.hasSlotController.test("hint", "withHint");
		const hasLabel = this.label ? true : !!hasLabelSlot;
		const hasHint = this.hint ? true : !!hasHintSlot;
		return b`
      <fieldset
        part="form-control"
        class=${e$3({
			"form-control": true,
			"form-control-radio-group": true,
			"form-control-has-label": hasLabel
		})}
        role="radiogroup"
        aria-labelledby="label"
        aria-describedby="hint"
        aria-errormessage="error-message"
        aria-orientation=${this.orientation}
      >
        <label
          part="form-control-label"
          id="label"
          class=${e$3({
			label: true,
			"has-label": hasLabel
		})}
          aria-hidden=${hasLabel ? "false" : "true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <slot part="form-control-input" @slotchange=${this.syncRadioElements}></slot>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${e$3({ "has-slotted": hasHint })}
          aria-hidden=${hasHint ? "false" : "true"}
          >${this.hint}</slot
        >
      </fieldset>
    `;
	}
};
WaRadioGroup.css = [
	size_styles_default,
	form_control_styles_default,
	radio_group_styles_default
];
WaRadioGroup.shadowRootOptions = {
	...WebAwesomeFormAssociatedElement.shadowRootOptions,
	delegatesFocus: true
};
__decorateClass([e$5("slot:not([name])")], WaRadioGroup.prototype, "defaultSlot", 2);
__decorateClass([n$2()], WaRadioGroup.prototype, "label", 2);
__decorateClass([n$2({ attribute: "hint" })], WaRadioGroup.prototype, "hint", 2);
__decorateClass([n$2({ reflect: true })], WaRadioGroup.prototype, "name", 2);
__decorateClass([n$2({ type: Boolean })], WaRadioGroup.prototype, "disabled", 2);
__decorateClass([n$2({ reflect: true })], WaRadioGroup.prototype, "orientation", 2);
__decorateClass([r$2()], WaRadioGroup.prototype, "value", 1);
__decorateClass([n$2({
	attribute: "value",
	reflect: true
})], WaRadioGroup.prototype, "defaultValue", 2);
__decorateClass([n$2({ reflect: true })], WaRadioGroup.prototype, "size", 2);
__decorateClass([watch("size")], WaRadioGroup.prototype, "handleSizeChange", 1);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaRadioGroup.prototype, "required", 2);
__decorateClass([n$2({
	type: Boolean,
	attribute: "with-label"
})], WaRadioGroup.prototype, "withLabel", 2);
__decorateClass([n$2({
	type: Boolean,
	attribute: "with-hint"
})], WaRadioGroup.prototype, "withHint", 2);
WaRadioGroup = __decorateClass([t$2("wa-radio-group")], WaRadioGroup);
WaRadioGroup.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/components/radio-group/radio-group.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.BXKMHNCQ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var select_styles_default = i$7`
  :host {
    --tag-max-size: 10ch;
    --show-duration: var(--wa-transition-fast);
    --hide-duration: var(--wa-transition-fast);
  }

  /* Add ellipses to multi select options */
  :host wa-tag::part(content) {
    display: initial;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
    max-width: var(--tag-max-size);
  }

  :host .disabled [part~='combobox'] {
    opacity: 0.5;
    cursor: not-allowed;
    outline: none;
  }

  :host .enabled:is(.open, :focus-within) [part~='combobox'] {
    outline-color: var(--wa-color-focus);
  }

  /** The popup */
  .select {
    flex: 1 1 auto;
    display: inline-flex;
    width: 100%;
    position: relative;
    vertical-align: middle;

    /* Pass through from select to the popup */
    --show-duration: inherit;
    --hide-duration: inherit;

    &::part(popup) {
      z-index: 900;
    }

    &[data-current-placement^='top']::part(popup) {
      transform-origin: bottom;
    }

    &[data-current-placement^='bottom']::part(popup) {
      transform-origin: top;
    }
  }

  /* Combobox */
  .combobox {
    flex: 1;
    display: flex;
    width: 100%;
    min-width: 0;
    align-items: center;
    justify-content: start;

    min-height: var(--wa-form-control-height);

    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    color: var(--wa-form-control-value-color);
    cursor: pointer;
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    overflow: hidden;
    padding: 0 var(--wa-form-control-padding-inline);
    position: relative;
    vertical-align: middle;
    transition:
      background-color var(--wa-transition-normal),
      border-color var(--wa-transition-normal),
      outline-color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    /* Pills */
    :host([pill]) & {
      border-radius: var(--wa-border-radius-pill);
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .combobox {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .combobox {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .combobox {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  .display-input {
    position: relative;
    width: 100%;
    font: inherit;
    border: none;
    background: none;
    line-height: var(--wa-form-control-value-line-height);
    color: var(--wa-form-control-value-color);
    cursor: inherit;
    overflow: hidden;
    padding: 0;
    margin: 0;
    -webkit-appearance: none;

    &:focus {
      outline: none;
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
    }
  }

  /*
   * Tags can be any content, so check for a non-empty container rather than wa-tag. has-selection forces a restyle
   * when the selection changes, since WebKit doesn't re-evaluate :has(:not(:empty)) when tags are cleared.
   */
  .select.multiple.has-selection {
    --_padding-with-tags: calc(var(--wa-form-control-height) * 0.1 - var(--wa-form-control-border-width));

    & .combobox:has(.tags:not(:empty)) {
      padding-block: var(--_padding-with-tags);
      padding-inline-start: var(--_padding-with-tags);
    }
  }

  /* Visually hide the display input when multiple is enabled */
  .select.multiple.has-selection .combobox:has(.tags:not(:empty)) .display-input {
    position: absolute;
    z-index: -1;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
  }

  .value-input {
    position: absolute;
    z-index: -1;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    padding: 0;
    margin: 0;
  }

  .tags {
    display: flex;
    flex: 1;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.25em;

    /* Nested inside the box, so a step down from the box's radius */
    & wa-tag:not([pill]) {
      border-radius: var(--wa-border-radius-s);
    }

    .disabled & {
      cursor: not-allowed !important;
    }
  }

  /* Start and End */

  .start,
  .end {
    flex: 0;
    display: inline-flex;
    align-items: center;
    color: var(--wa-color-neutral-on-quiet);
  }

  .end::slotted(*) {
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  .start::slotted(*) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  .select.multiple.has-selection .combobox:has(.tags:not(:empty)) .start::slotted(*) {
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - var(--_padding-with-tags));
  }

  /* Clear button */
  [part~='clear-button'] {
    flex: 0 0 auto;
    display: inline-flex;
    align-self: stretch;
    align-items: center;
    justify-content: center;
    inline-size: 1.5em;
    font-size: inherit;
    color: var(--wa-color-neutral-on-quiet);
    border: none;
    background: none;
    padding: 0;
    transition: color var(--wa-transition-normal);
    cursor: pointer;
    /* The box is wider than the glyph, so overhang half that growth on each side. Keeps the glyph
       on the same trailing axis as the segmented-field pickers' clear buttons. */
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - 0.125em);
    margin-inline-end: -0.125em;

    &:focus {
      outline: none;
    }

    @media (hover: hover) {
      &:hover {
        color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
      }
    }

    &:active {
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
    }
  }

  /* Expand icon */
  .expand-icon {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    color: var(--wa-color-neutral-on-quiet);
    transition: rotate var(--wa-transition-slow) var(--wa-transition-easing);
    rotate: 0deg;
    margin-inline-start: var(--wa-form-control-padding-inline);

    .open & {
      rotate: -180deg;
    }
  }

  /* Listbox */
  .listbox {
    display: block;
    position: relative;
    font: inherit;
    box-shadow: var(--wa-shadow-m);
    background: var(--wa-color-surface-raised);
    border-color: var(--wa-color-surface-border);
    border-radius: var(--wa-border-radius-m);
    border-style: var(--wa-border-style);
    border-width: var(--wa-border-width-s);
    padding: 0.25em;
    overflow: auto;
    overscroll-behavior: none;

    /* Make sure it adheres to the popup's auto size */
    max-width: var(--auto-size-available-width);
    max-height: var(--auto-size-available-height);

    &::slotted(wa-divider) {
      --spacing: 0.5em;
    }
  }

  /* Space options with half the listbox's padding */
  .listbox slot:not([name]) {
    display: flex;
    flex-direction: column;
    gap: 0.125em;
  }

  slot:not([name])::slotted(small) {
    display: block;
    font-size: var(--wa-font-size-smaller);
    font-weight: var(--wa-font-weight-semibold);
    color: var(--wa-color-text-quiet);
    padding-block: 0.5em;
    padding-inline: 2.25em;
  }
`;
// node_modules/lit-html/directives/unsafe-html.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/ var e$1 = class extends i$3 {
	constructor(i) {
		if (super(i), this.it = A, i.type !== t$1.CHILD) throw Error(this.constructor.directiveName + "() can only be used in child bindings");
	}
	render(r) {
		if (r === A || null == r) return this._t = void 0, this.it = r;
		if (r === E) return r;
		if ("string" != typeof r) throw Error(this.constructor.directiveName + "() called with a non-string value");
		if (r === this.it) return this._t;
		this.it = r;
		const s = [r];
		return s.raw = s, this._t = {
			_$litType$: this.constructor.resultType,
			strings: s,
			values: []
		};
	}
};
e$1.directiveName = "unsafeHTML", e$1.resultType = 1;
var o = e$4(e$1);
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.M22PYPNQ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaSelect = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super(...arguments);
		this.assumeInteractionOn = ["blur", "input"];
		this.cachedOptions = null;
		this.hasSlotController = new HasSlotController(this, "hint", "label");
		this.localize = new LocalizeController(this);
		this.selectionOrder = /* @__PURE__ */ new Map();
		this.typeToSelectString = "";
		this.slotChangePending = false;
		this.displayLabel = "";
		this.selectedOptions = [];
		this.name = "";
		this._defaultValue = null;
		this.size = "m";
		this.placeholder = "";
		this.multiple = false;
		this.maxOptionsVisible = 3;
		this.disabled = false;
		this.withClear = false;
		this.open = false;
		this.appearance = "outlined";
		this.pill = false;
		this.label = "";
		this.placement = "bottom";
		this.hint = "";
		this.withLabel = false;
		this.withHint = false;
		this.required = false;
		this.getTag = (option) => {
			return b`
        <wa-tag
          part="tag"
          exportparts="
            content:tag__content,
            remove-button:tag__remove-button,
            remove-button__base:tag__remove-button__base,
            remove-button__button:tag__remove-button__button
          "
          ?pill=${this.pill}
          size=${this.size}
          with-remove
          data-value=${option.value}
          @wa-remove=${(event) => this.handleTagRemove(event, option)}
        >
          ${option.label}
        </wa-tag>
      `;
		};
		this.handleDocumentFocusIn = (event) => {
			const path = event.composedPath();
			if (this && !path.includes(this)) this.hide();
		};
		this.handleDocumentKeyDown = (event) => {
			const target = event.target;
			const isClearButton = target.closest("[part~=\"clear-button\"]") !== null;
			const isButton = target.closest("wa-button") !== null;
			if (isClearButton || isButton) return;
			if (event.key === "Escape" && this.open && isTopDismissible(this)) {
				event.preventDefault();
				event.stopPropagation();
				this.hide();
				this.displayInput.focus({ preventScroll: true });
			}
			if (event.key === "Enter" || event.key === " " && this.typeToSelectString === "") {
				event.preventDefault();
				event.stopImmediatePropagation();
				if (!this.open) {
					this.show();
					return;
				}
				if (this.currentOption && !this.currentOption.disabled) {
					this.valueHasChanged = true;
					this.hasInteracted = true;
					if (this.multiple) this.toggleOptionSelection(this.currentOption);
					else this.setSelectedOptions(this.currentOption);
					this.updateComplete.then(() => {
						this.dispatchEvent(new InputEvent("input", {
							bubbles: true,
							composed: true
						}));
						this.dispatchEvent(new Event("change", {
							bubbles: true,
							composed: true
						}));
					});
					if (!this.multiple) {
						this.hide();
						this.displayInput.focus({ preventScroll: true });
					}
				}
				return;
			}
			if ([
				"ArrowUp",
				"ArrowDown",
				"Home",
				"End"
			].includes(event.key)) {
				const allOptions = this.getAllOptions();
				const currentIndex = allOptions.indexOf(this.currentOption);
				let newIndex = Math.max(0, currentIndex);
				event.preventDefault();
				if (!this.open) {
					this.show();
					if (this.currentOption) return;
				}
				if (event.key === "ArrowDown") {
					newIndex = currentIndex + 1;
					if (newIndex > allOptions.length - 1) newIndex = 0;
				} else if (event.key === "ArrowUp") {
					newIndex = currentIndex - 1;
					if (newIndex < 0) newIndex = allOptions.length - 1;
				} else if (event.key === "Home") newIndex = 0;
				else if (event.key === "End") newIndex = allOptions.length - 1;
				this.setCurrentOption(allOptions[newIndex]);
			}
			if (event.key?.length === 1 || event.key === "Backspace") {
				const allOptions = this.getAllOptions();
				if (event.metaKey || event.ctrlKey || event.altKey) return;
				if (!this.open) {
					if (event.key === "Backspace") return;
					this.show();
				}
				event.stopPropagation();
				event.preventDefault();
				clearTimeout(this.typeToSelectTimeout);
				this.typeToSelectTimeout = window.setTimeout(() => this.typeToSelectString = "", 1e3);
				if (event.key === "Backspace") this.typeToSelectString = this.typeToSelectString.slice(0, -1);
				else this.typeToSelectString += event.key.toLowerCase();
				for (const option of allOptions) if (option.label.toLowerCase().startsWith(this.typeToSelectString)) {
					this.setCurrentOption(option);
					break;
				}
			}
		};
		this.handleDocumentMouseDown = (event) => {
			const path = event.composedPath();
			if (this && !path.includes(this)) this.hide();
		};
	}
	static get validators() {
		const validators = [RequiredValidator({ validationElement: Object.assign(document.createElement("select"), { required: true }) })];
		return [...super.validators, ...validators];
	}
	/** Where to anchor native constraint validation */
	get validationTarget() {
		return this.valueInput;
	}
	set defaultValue(val) {
		this._defaultValue = this.convertDefaultValue(val);
	}
	get defaultValue() {
		return this.convertDefaultValue(this._defaultValue);
	}
	rawValuesEqual(a, b) {
		if (a == null && b == null) return true;
		if (a == null || b == null) return false;
		if (a.length !== b.length) return false;
		return a.every((v, i) => v === b[i]);
	}
	/**
	* @private
	* A converter for defaultValue from array to string if its multiple. Also fixes some hydration issues.
	*/
	convertDefaultValue(val) {
		if (!(this.multiple || this.hasAttribute("multiple")) && Array.isArray(val)) val = val[0];
		return val;
	}
	set value(val) {
		let oldValue = this.value;
		if (val instanceof FormData) val = val.getAll(this.name);
		if (val != null && !Array.isArray(val)) val = [val];
		const oldRawValue = this._value;
		this._value = val ?? null;
		if (!this.rawValuesEqual(oldRawValue, this._value)) {
			this.valueHasChanged = true;
			this.requestUpdate("value", oldValue);
		}
	}
	get value() {
		let value = this._value ?? this.defaultValue ?? null;
		if (value != null) value = Array.isArray(value) ? value : [value];
		this.optionValues = new Set(this.getAllOptions().filter((option) => !option.disabled).map((option) => option.value));
		let ret = value;
		if (value != null) {
			ret = value.filter((v) => this.optionValues.has(v));
			ret = this.multiple ? ret : ret[0];
			ret = ret ?? null;
		}
		return ret;
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	connectedCallback() {
		super.connectedCallback();
		this.processSlotChange();
		this.open = false;
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		this.removeOpenListeners();
		this.cachedOptions = null;
	}
	updateDefaultValue() {
		const defaultSelectedOptions = this.getAllOptions().filter((el) => el.hasAttribute("selected") || el.defaultSelected);
		if (defaultSelectedOptions.length > 0) {
			const selectedValues = defaultSelectedOptions.map((el) => el.value);
			this._defaultValue = this.multiple ? selectedValues : selectedValues[0];
		}
		if (this.hasAttribute("value")) this._defaultValue = this.getAttribute("value") || null;
	}
	addOpenListeners() {
		document.addEventListener("focusin", this.handleDocumentFocusIn);
		document.addEventListener("keydown", this.handleDocumentKeyDown);
		document.addEventListener("mousedown", this.handleDocumentMouseDown);
		registerDismissible(this);
		if (this.getRootNode() !== document) this.getRootNode().addEventListener("focusin", this.handleDocumentFocusIn);
	}
	removeOpenListeners() {
		document.removeEventListener("focusin", this.handleDocumentFocusIn);
		document.removeEventListener("keydown", this.handleDocumentKeyDown);
		document.removeEventListener("mousedown", this.handleDocumentMouseDown);
		unregisterDismissible(this);
		if (this.getRootNode() !== document) this.getRootNode().removeEventListener("focusin", this.handleDocumentFocusIn);
	}
	handleFocus() {
		this.displayInput.setSelectionRange(0, 0);
	}
	handleLabelClick() {
		this.displayInput.focus();
	}
	handleComboboxClick(event) {
		event.preventDefault();
	}
	handleComboboxMouseDown(event) {
		const isButton = event.composedPath().some((el) => el instanceof Element && el.tagName.toLowerCase() === "wa-button");
		if (this.disabled || isButton) return;
		event.preventDefault();
		this.displayInput.focus({ preventScroll: true });
		this.open = !this.open;
	}
	handleComboboxKeyDown(event) {
		event.stopPropagation();
		this.handleDocumentKeyDown(event);
	}
	handleClearClick(event) {
		event.stopPropagation();
		this.hasInteracted = true;
		this.valueHasChanged = true;
		if (this.value !== null) {
			this.displayLabel = "";
			this.selectionOrder.clear();
			this.setSelectedOptions([]);
			this.displayInput.focus({ preventScroll: true });
			this.updateComplete.then(() => {
				this.dispatchEvent(new WaClearEvent());
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
			});
		}
	}
	handleClearMouseDown(event) {
		event.stopPropagation();
		event.preventDefault();
	}
	handleOptionClick(event) {
		const option = event.target.closest("wa-option");
		if (option && !option.disabled) {
			this.hasInteracted = true;
			this.valueHasChanged = true;
			if (this.multiple) this.toggleOptionSelection(option);
			else this.setSelectedOptions(option);
			this.updateComplete.then(() => this.displayInput.focus({ preventScroll: true }));
			this.requestUpdate("value");
			this.updateComplete.then(() => {
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
			});
			if (!this.multiple) {
				this.hide();
				this.displayInput.focus({ preventScroll: true });
			}
		}
	}
	handleDefaultSlotChange() {
		if (this.slotChangePending) return;
		this.slotChangePending = true;
		queueMicrotask(() => {
			this.slotChangePending = false;
			this.processSlotChange();
		});
	}
	processSlotChange() {
		if (!customElements.get("wa-option")) customElements.whenDefined("wa-option").then(() => this.handleDefaultSlotChange());
		if (this.didSSR && !this.hasUpdated) {
			this.updateComplete.then(() => {
				this.handleDefaultSlotChange();
			});
			return;
		}
		this.cachedOptions = null;
		const allOptions = this.getAllOptions();
		this.updateDefaultValue();
		let value = this.value;
		if (value == null || !this.valueHasChanged && !this.hasInteracted) {
			this.selectionChanged();
			return;
		}
		if (!Array.isArray(value)) value = [value];
		const selectedOptions = allOptions.filter((el) => value.includes(el.value));
		this.setSelectedOptions(selectedOptions);
	}
	handleTagRemove(event, directOption) {
		event.stopPropagation();
		if (this.disabled) return;
		this.hasInteracted = true;
		this.valueHasChanged = true;
		let option = directOption;
		if (!option) {
			const tagElement = event.target.closest("wa-tag[data-value]");
			if (tagElement) {
				const value = tagElement.dataset.value;
				option = this.selectedOptions.find((opt) => opt.value === value);
			}
		}
		if (option) {
			this.toggleOptionSelection(option, false);
			this.updateComplete.then(() => {
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
			});
		}
	}
	getAllOptions() {
		if (this.cachedOptions) return this.cachedOptions;
		if (!this?.querySelectorAll) return [];
		this.cachedOptions = [...this.querySelectorAll("wa-option")];
		return this.cachedOptions;
	}
	getFirstOption() {
		return this.querySelector("wa-option");
	}
	setCurrentOption(option) {
		this.getAllOptions().forEach((el) => {
			el.current = false;
			el.tabIndex = -1;
		});
		if (option) {
			this.currentOption = option;
			option.current = true;
			option.tabIndex = 0;
			option.focus({ preventScroll: true });
			if (this.open && !this.listbox.hidden) scrollIntoView(option, this.listbox, "vertical", "auto");
		}
	}
	setSelectedOptions(option) {
		const allOptions = this.getAllOptions();
		const newSelectedOptions = Array.isArray(option) ? option : [option];
		allOptions.forEach((el) => {
			if (newSelectedOptions.includes(el)) return;
			el.selected = false;
		});
		if (newSelectedOptions.length) newSelectedOptions.forEach((el) => el.selected = true);
		this.selectionChanged();
	}
	toggleOptionSelection(option, force) {
		if (force === true || force === false) option.selected = force;
		else option.selected = !option.selected;
		this.selectionChanged();
	}
	selectionChanged() {
		const newSelectedOptions = this.getAllOptions().filter((el) => {
			if (!this.hasInteracted && !this.valueHasChanged) {
				const defaultValue = this.defaultValue;
				const defaultValues = Array.isArray(defaultValue) ? defaultValue : [defaultValue];
				return el.hasAttribute("selected") || el.defaultSelected || el.selected || defaultValues?.includes(el.value);
			}
			return el.selected;
		});
		const newSelectedValues = new Set(newSelectedOptions.map((el) => el.value));
		for (const value of this.selectionOrder.keys()) if (!newSelectedValues.has(value)) this.selectionOrder.delete(value);
		let nextOrder = (this.selectionOrder.size > 0 ? Math.max(...this.selectionOrder.values()) : -1) + 1;
		for (const option of newSelectedOptions) if (!this.selectionOrder.has(option.value)) this.selectionOrder.set(option.value, nextOrder++);
		this.selectedOptions = newSelectedOptions.sort((a, b) => {
			return (this.selectionOrder.get(a.value) ?? 0) - (this.selectionOrder.get(b.value) ?? 0);
		});
		let selectedValues = new Set(this.selectedOptions.map((el) => el.value));
		if (selectedValues.size > 0 || this._value) {
			const oldValue = this._value;
			if (this._value == null) {
				let value = this.defaultValue ?? [];
				this._value = Array.isArray(value) ? value : [value];
			}
			this._value = this._value?.filter((value) => !this.optionValues?.has(value)) ?? null;
			this._value?.unshift(...selectedValues);
			this.requestUpdate("value", oldValue);
		}
		if (this.multiple) {
			if (this.placeholder && !this.value?.length) this.displayLabel = "";
			else this.displayLabel = this.localize.term("numOptionsSelected", this.selectedOptions.length);
		} else {
			const selectedOption = this.selectedOptions[0];
			this.displayLabel = selectedOption?.label ?? "";
		}
		this.updateComplete.then(() => {
			this.updateValidity();
		});
	}
	get tags() {
		return this.selectedOptions.map((option, index) => {
			if (index < this.maxOptionsVisible || this.maxOptionsVisible <= 0) {
				const tag = this.getTag(option, index);
				if (!tag) return null;
				return typeof tag === "string" ? o(tag) : tag;
			} else if (index === this.maxOptionsVisible) return b`
          <wa-tag
            part="tag"
            exportparts="
              content:tag__content,
              remove-button:tag__remove-button,
              remove-button__base:tag__remove-button__base,
              remove-button__button:tag__remove-button__button
            "
            ?pill=${this.pill}
            size=${this.size}
            >+${this.selectedOptions.length - index}</wa-tag
          >
        `;
			return null;
		});
	}
	updated(changedProperties) {
		super.updated(changedProperties);
		if (changedProperties.has("value") || changedProperties.has("displayLabel")) this.customStates.set("blank", !this.value && !this.displayLabel);
	}
	handleDisabledChange() {
		if (this.disabled && this.open) this.open = false;
	}
	handleValueChange() {
		const allOptions = this.getAllOptions();
		const value = Array.isArray(this.value) ? this.value : [this.value];
		const selectedOptions = allOptions.filter((el) => value.includes(el.value));
		this.setSelectedOptions(selectedOptions);
		this.updateValidity();
	}
	async handleOpenChange() {
		if (this.open && !this.disabled) {
			this.setCurrentOption(this.selectedOptions[0] || this.getFirstOption());
			const waShowEvent = new WaShowEvent();
			this.dispatchEvent(waShowEvent);
			if (waShowEvent.defaultPrevented) {
				this.open = false;
				return;
			}
			this.addOpenListeners();
			this.listbox.hidden = false;
			this.popup.active = true;
			requestAnimationFrame(() => {
				this.setCurrentOption(this.currentOption);
			});
			await animateWithClass(this.popup.popup, "show");
			if (this.currentOption) scrollIntoView(this.currentOption, this.listbox, "vertical", "auto");
			this.dispatchEvent(new WaAfterShowEvent());
		} else {
			const waHideEvent = new WaHideEvent();
			this.dispatchEvent(waHideEvent);
			if (waHideEvent.defaultPrevented) {
				this.open = false;
				return;
			}
			this.removeOpenListeners();
			await animateWithClass(this.popup.popup, "hide");
			this.listbox.hidden = true;
			this.popup.active = false;
			this.dispatchEvent(new WaAfterHideEvent());
		}
	}
	/** Shows the listbox. */
	async show() {
		if (this.open || this.disabled) {
			this.open = false;
			return;
		}
		this.open = true;
		return waitForEvent(this, "wa-after-show");
	}
	/** Hides the listbox. */
	async hide() {
		if (!this.open || this.disabled) {
			this.open = false;
			return;
		}
		this.open = false;
		return waitForEvent(this, "wa-after-hide");
	}
	/** Sets focus on the control. */
	focus(options) {
		this.displayInput.focus(options);
	}
	/** Removes focus from the control. */
	blur() {
		this.displayInput.blur();
	}
	formResetCallback() {
		this.selectionOrder.clear();
		this.value = this.defaultValue;
		super.formResetCallback();
		this.handleValueChange();
		this.updateComplete.then(() => {
			this.dispatchEvent(new InputEvent("input", {
				bubbles: true,
				composed: true
			}));
			this.dispatchEvent(new Event("change", {
				bubbles: true,
				composed: true
			}));
		});
	}
	render() {
		const hasLabelSlot = this.hasSlotController.test("label", "withLabel");
		const hasHintSlot = this.hasSlotController.test("hint", "withHint");
		const hasLabel = this.label ? true : !!hasLabelSlot;
		const hasHint = this.hint ? true : !!hasHintSlot;
		const hasClearIcon = (this.hasUpdated || false) && this.withClear && !this.disabled && (this.displayLabel || this.value && this.value.length > 0);
		return b`
      <div
        part="form-control"
        class=${e$3({
			"form-control": true,
			"form-control-has-label": hasLabel
		})}
      >
        <label
          id="label"
          part="form-control-label label"
          class=${e$3({
			label: true,
			"has-label": hasLabel
		})}
          aria-hidden=${hasLabel ? "false" : "true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <div part="form-control-input" class="form-control-input">
          <wa-popup
            class=${e$3({
			select: true,
			open: this.open,
			disabled: this.disabled,
			enabled: !this.disabled,
			multiple: this.multiple,
			"has-selection": this.selectedOptions.length > 0
		})}
            placement=${this.placement}
            flip
            shift
            sync="width"
            auto-size="vertical"
            auto-size-padding="10"
          >
            <div
              part="combobox"
              class="combobox"
              slot="anchor"
              @keydown=${this.handleComboboxKeyDown}
              @mousedown=${this.handleComboboxMouseDown}
              @click=${this.handleComboboxClick}
            >
              <slot part="start" name="start" class="start"></slot>

              <input
                part="display-input"
                class="display-input"
                type="text"
                placeholder=${this.placeholder}
                .disabled=${this.disabled}
                .value=${this.displayLabel}
                ?required=${this.required}
                autocomplete="off"
                spellcheck="false"
                autocapitalize="off"
                readonly
                aria-invalid=${!this.validity.valid}
                aria-controls="listbox"
                aria-expanded=${this.open ? "true" : "false"}
                aria-haspopup="listbox"
                aria-labelledby="label"
                aria-disabled=${this.disabled ? "true" : "false"}
                aria-describedby="hint"
                role="combobox"
                tabindex="0"
                @focus=${this.handleFocus}
              />

              <!-- Tags need to wait for first hydration before populating otherwise it will create a hydration mismatch. -->
              ${this.multiple && this.hasUpdated ? b`<div part="tags" class="tags" @wa-remove=${this.handleTagRemove}>${this.tags}</div>` : ""}

              <input
                class="value-input"
                type="text"
                ?disabled=${this.disabled}
                ?required=${this.required}
                .value=${Array.isArray(this.value) ? this.value.join(", ") : this.value}
                tabindex="-1"
                aria-hidden="true"
                @focus=${() => this.focus()}
              />

              ${hasClearIcon ? b`
                    <button
                      part="clear-button"
                      type="button"
                      aria-label=${this.localize.term("clearEntry")}
                      @mousedown=${this.handleClearMouseDown}
                      @click=${this.handleClearClick}
                      tabindex="-1"
                    >
                      <slot name="clear-icon">
                        <wa-icon name="circle-xmark" library="system" variant="regular"></wa-icon>
                      </slot>
                    </button>
                  ` : ""}

              <slot name="end" part="end" class="end"></slot>

              <slot name="expand-icon" part="expand-icon" class="expand-icon">
                <wa-icon library="system" name="chevron-down" variant="solid"></wa-icon>
              </slot>
            </div>

            <div
              id="listbox"
              role="listbox"
              aria-expanded=${this.open ? "true" : "false"}
              aria-multiselectable=${this.multiple ? "true" : "false"}
              aria-labelledby="label"
              part="listbox"
              class="listbox"
              tabindex="-1"
              @mouseup=${this.handleOptionClick}
            >
              <slot @slotchange=${this.handleDefaultSlotChange}></slot>
            </div>
          </wa-popup>
        </div>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${e$3({ "has-slotted": hasHint })}
          aria-hidden=${hasHint ? "false" : "true"}
          >${this.hint}</slot
        >
      </div>
    `;
	}
};
WaSelect.css = [
	select_styles_default,
	form_control_styles_default,
	size_styles_default
];
__decorateClass([e$5(".select")], WaSelect.prototype, "popup", 2);
__decorateClass([e$5(".combobox")], WaSelect.prototype, "combobox", 2);
__decorateClass([e$5(".display-input")], WaSelect.prototype, "displayInput", 2);
__decorateClass([e$5(".value-input")], WaSelect.prototype, "valueInput", 2);
__decorateClass([e$5(".listbox")], WaSelect.prototype, "listbox", 2);
__decorateClass([r$2()], WaSelect.prototype, "displayLabel", 2);
__decorateClass([r$2()], WaSelect.prototype, "currentOption", 2);
__decorateClass([r$2()], WaSelect.prototype, "selectedOptions", 2);
__decorateClass([n$2({ reflect: true })], WaSelect.prototype, "name", 2);
__decorateClass([n$2({ attribute: false })], WaSelect.prototype, "defaultValue", 1);
__decorateClass([n$2({
	attribute: "value",
	reflect: false
})], WaSelect.prototype, "value", 1);
__decorateClass([n$2({ reflect: true })], WaSelect.prototype, "size", 2);
__decorateClass([watch("size")], WaSelect.prototype, "handleSizeChange", 1);
__decorateClass([n$2()], WaSelect.prototype, "placeholder", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaSelect.prototype, "multiple", 2);
__decorateClass([n$2({
	attribute: "max-options-visible",
	type: Number
})], WaSelect.prototype, "maxOptionsVisible", 2);
__decorateClass([n$2({ type: Boolean })], WaSelect.prototype, "disabled", 2);
__decorateClass([n$2({
	attribute: "with-clear",
	type: Boolean
})], WaSelect.prototype, "withClear", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaSelect.prototype, "open", 2);
__decorateClass([n$2({ reflect: true })], WaSelect.prototype, "appearance", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaSelect.prototype, "pill", 2);
__decorateClass([n$2()], WaSelect.prototype, "label", 2);
__decorateClass([n$2({ reflect: true })], WaSelect.prototype, "placement", 2);
__decorateClass([n$2({ attribute: "hint" })], WaSelect.prototype, "hint", 2);
__decorateClass([n$2({
	attribute: "with-label",
	type: Boolean
})], WaSelect.prototype, "withLabel", 2);
__decorateClass([n$2({
	attribute: "with-hint",
	type: Boolean
})], WaSelect.prototype, "withHint", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaSelect.prototype, "required", 2);
__decorateClass([n$2({ attribute: false })], WaSelect.prototype, "getTag", 2);
__decorateClass([watch("disabled", { waitUntilFirstUpdate: true })], WaSelect.prototype, "handleDisabledChange", 1);
__decorateClass([watch("value", { waitUntilFirstUpdate: true })], WaSelect.prototype, "handleValueChange", 1);
__decorateClass([watch("open", { waitUntilFirstUpdate: true })], WaSelect.prototype, "handleOpenChange", 1);
WaSelect = __decorateClass([t$2("wa-select")], WaSelect);
WaSelect.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.HPULLNVR.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaRemoveEvent = class extends Event {
	constructor() {
		super("wa-remove", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.DC5HFJMQ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var tag_styles_default = i$7`
  @layer wa-component {
    :host {
      display: inline-flex;
      gap: 0.5em;
      border-radius: var(--wa-border-radius-m);
      align-items: center;
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
      border-style: var(--wa-border-style);
      border-width: var(--wa-border-width-s);
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      font-size: inherit;
      line-height: 1;
      white-space: nowrap;
      user-select: none;
      -webkit-user-select: none;
      height: calc(var(--wa-form-control-height) * 0.8);
      line-height: calc(var(--wa-form-control-height) - var(--wa-form-control-border-width) * 2);
      padding: 0 0.75em;
    }

    /* Appearance modifiers */
    :host([appearance='outlined']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: var(--wa-color-border-loud, var(--wa-color-neutral-border-loud));
    }

    :host([appearance='filled']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: transparent;
    }

    :host([appearance='filled-outlined']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
    }

    :host([appearance='accent']) {
      color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
      background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));
      border-color: transparent;
    }
  }

  .content {
    font-size: var(--wa-font-size-smaller);
  }

  [part='remove-button'] {
    line-height: 1;
  }

  [part='remove-button']::part(button) {
    padding: 0;
    height: 1em;
    width: 1em;
    color: currentColor;
  }

  @media (hover: hover) {
    :host(:hover) > [part='remove-button']::part(button) {
      background-color: transparent;
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
    }
  }

  :host(:active) > [part='remove-button']::part(button) {
    background-color: transparent;
    color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
  }

  /*
   * Pill modifier
   */
  :host([pill]) {
    border-radius: var(--wa-border-radius-pill);
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.NTHRIVL2.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaTag = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
		this.variant = "neutral";
		this.appearance = "filled-outlined";
		this.size = "m";
		this.pill = false;
		this.withRemove = false;
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	handleRemoveClick() {
		this.dispatchEvent(new WaRemoveEvent());
	}
	render() {
		return b`
      <slot part="content" class="content"></slot>

      ${this.withRemove ? b`
            <wa-button
              part="remove-button"
              exportparts="base:remove-button__base, button:remove-button__button"
              class="remove"
              appearance="plain"
              size=${this.size}
              @click=${this.handleRemoveClick}
              tabindex="-1"
            >
              <wa-icon name="xmark" library="system" variant="solid" label=${this.localize.term("remove")}></wa-icon>
            </wa-button>
          ` : ""}
    `;
	}
};
WaTag.css = [
	tag_styles_default,
	variants_styles_default,
	size_styles_default
];
__decorateClass([n$2({ reflect: true })], WaTag.prototype, "variant", 2);
__decorateClass([n$2({ reflect: true })], WaTag.prototype, "appearance", 2);
__decorateClass([n$2({ reflect: true })], WaTag.prototype, "size", 2);
__decorateClass([watch("size")], WaTag.prototype, "handleSizeChange", 1);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaTag.prototype, "pill", 2);
__decorateClass([n$2({
	attribute: "with-remove",
	type: Boolean
})], WaTag.prototype, "withRemove", 2);
WaTag = __decorateClass([t$2("wa-tag")], WaTag);
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.ZWQCGLB5.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaRepositionEvent = class extends Event {
	constructor() {
		super("wa-reposition", {
			bubbles: true,
			cancelable: false,
			composed: true
		});
	}
};
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.HS5AYC6E.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var popup_styles_default = i$7`
  :host {
    --arrow-color: black;
    --arrow-size: var(--wa-tooltip-arrow-size);
    --popup-border-width: 0px;
    --show-duration: var(--wa-transition-fast);
    --hide-duration: var(--wa-transition-fast);

    /*
     * These properties are computed to account for the arrow's dimensions after being rotated 45º. The constant
     * 0.7071 is derived from sin(45) to calculate the length of the arrow after rotation.
     *
     * The diamond will be translated inward by --arrow-base-offset, the border thickness, to centralise it on
     * the inner edge of the popup border. This also means we need to increase the size of the arrow by the
     * same amount to compensate.
     *
     * A diamond shaped clipping mask is used to avoid overlap of popup content. This extends slightly inward so
     * the popup border is covered with no sub-pixel rounding artifacts. The diamond corners are mitred at 22.5º
     * to properly merge any arrow border with the popup border. The constant 1.4142 is derived from 1 + tan(22.5).
     *
     */
    --arrow-base-offset: var(--popup-border-width);
    --arrow-size-diagonal: calc((var(--arrow-size) + var(--arrow-base-offset)) * 0.7071);
    --arrow-padding-offset: calc(var(--arrow-size-diagonal) - var(--arrow-size));
    --arrow-size-div: calc(var(--arrow-size-diagonal) * 2);
    --arrow-clipping-corner: calc(var(--arrow-base-offset) * 1.4142);

    display: contents;
  }

  .popup {
    position: absolute;
    isolation: isolate;
    max-width: var(--auto-size-available-width, none);
    max-height: var(--auto-size-available-height, none);

    /* Clear UA styles for [popover] */
    :where(&) {
      inset: unset;
      padding: unset;
      margin: unset;
      width: unset;
      height: unset;
      color: unset;
      background: unset;
      border: unset;
      overflow: unset;
    }
  }

  .popup-fixed {
    position: fixed;
  }

  .popup:not(.popup-active) {
    display: none;
  }

  .arrow {
    position: absolute;
    width: var(--arrow-size-div);
    height: var(--arrow-size-div);
    background: var(--arrow-color);
    z-index: 3;
    clip-path: polygon(
      var(--arrow-clipping-corner) 100%,
      var(--arrow-base-offset) calc(100% - var(--arrow-base-offset)),
      calc(var(--arrow-base-offset) - 2px) calc(100% - var(--arrow-base-offset)),
      calc(100% - var(--arrow-base-offset)) calc(var(--arrow-base-offset) - 2px),
      calc(100% - var(--arrow-base-offset)) var(--arrow-base-offset),
      100% var(--arrow-clipping-corner),
      100% 100%
    );
    rotate: 45deg;
  }

  :host([data-current-placement|='left']) .arrow {
    rotate: -45deg;
  }

  :host([data-current-placement|='right']) .arrow {
    rotate: 135deg;
  }

  :host([data-current-placement|='bottom']) .arrow {
    rotate: 225deg;
  }

  /* Hover bridge */
  .popup-hover-bridge:not(.popup-hover-bridge-visible) {
    display: none;
  }

  .popup-hover-bridge {
    position: fixed;
    z-index: 899;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    clip-path: polygon(
      var(--hover-bridge-top-left-x, 0) var(--hover-bridge-top-left-y, 0),
      var(--hover-bridge-top-right-x, 0) var(--hover-bridge-top-right-y, 0),
      var(--hover-bridge-bottom-right-x, 0) var(--hover-bridge-bottom-right-y, 0),
      var(--hover-bridge-bottom-left-x, 0) var(--hover-bridge-bottom-left-y, 0)
    );
  }

  /* Built-in animations */
  .show {
    animation: show var(--show-duration) ease;
  }

  .hide {
    animation: show var(--hide-duration) ease reverse;
  }

  @keyframes show {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .show-with-scale {
    animation: show-with-scale var(--show-duration) ease;
  }

  .hide-with-scale {
    animation: show-with-scale var(--hide-duration) ease reverse;
  }

  @keyframes show-with-scale {
    from {
      opacity: 0;
      scale: 0.8;
    }
    to {
      opacity: 1;
      scale: 1;
    }
  }
`;
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var min = Math.min;
var max = Math.max;
var round = Math.round;
var floor = Math.floor;
var createCoords = (v) => ({
	x: v,
	y: v
});
var oppositeSideMap = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function clamp(start, value, end) {
	return max(start, min(value, end));
}
function evaluate(value, param) {
	return typeof value === "function" ? value(param) : value;
}
function getSide(placement) {
	return placement.split("-")[0];
}
function getAlignment(placement) {
	return placement.split("-")[1];
}
function getOppositeAxis(axis) {
	return axis === "x" ? "y" : "x";
}
function getAxisLength(axis) {
	return axis === "y" ? "height" : "width";
}
function getSideAxis(placement) {
	const firstChar = placement[0];
	return firstChar === "t" || firstChar === "b" ? "y" : "x";
}
function getAlignmentAxis(placement) {
	return getOppositeAxis(getSideAxis(placement));
}
function getAlignmentSides(placement, rects, rtl) {
	if (rtl === void 0) rtl = false;
	const alignment = getAlignment(placement);
	const alignmentAxis = getAlignmentAxis(placement);
	const length = getAxisLength(alignmentAxis);
	let mainAlignmentSide = alignmentAxis === "x" ? alignment === (rtl ? "end" : "start") ? "right" : "left" : alignment === "start" ? "bottom" : "top";
	if (rects.reference[length] > rects.floating[length]) mainAlignmentSide = getOppositePlacement(mainAlignmentSide);
	return [mainAlignmentSide, getOppositePlacement(mainAlignmentSide)];
}
function getExpandedPlacements(placement) {
	const oppositePlacement = getOppositePlacement(placement);
	return [
		getOppositeAlignmentPlacement(placement),
		oppositePlacement,
		getOppositeAlignmentPlacement(oppositePlacement)
	];
}
function getOppositeAlignmentPlacement(placement) {
	return placement.includes("start") ? placement.replace("start", "end") : placement.replace("end", "start");
}
var lrPlacement = ["left", "right"];
var rlPlacement = ["right", "left"];
var tbPlacement = ["top", "bottom"];
var btPlacement = ["bottom", "top"];
function getSideList(side, isStart, rtl) {
	switch (side) {
		case "top":
		case "bottom":
			if (rtl) return isStart ? rlPlacement : lrPlacement;
			return isStart ? lrPlacement : rlPlacement;
		case "left":
		case "right": return isStart ? tbPlacement : btPlacement;
		default: return [];
	}
}
function getOppositeAxisPlacements(placement, flipAlignment, direction, rtl) {
	const alignment = getAlignment(placement);
	let list = getSideList(getSide(placement), direction === "start", rtl);
	if (alignment) {
		list = list.map((side) => side + "-" + alignment);
		if (flipAlignment) list = list.concat(list.map(getOppositeAlignmentPlacement));
	}
	return list;
}
function getOppositePlacement(placement) {
	const side = getSide(placement);
	return oppositeSideMap[side] + placement.slice(side.length);
}
function expandPaddingObject(padding) {
	var _padding$top, _padding$right, _padding$bottom, _padding$left;
	return {
		top: (_padding$top = padding.top) != null ? _padding$top : 0,
		right: (_padding$right = padding.right) != null ? _padding$right : 0,
		bottom: (_padding$bottom = padding.bottom) != null ? _padding$bottom : 0,
		left: (_padding$left = padding.left) != null ? _padding$left : 0
	};
}
function getPaddingObject(padding) {
	return typeof padding !== "number" ? expandPaddingObject(padding) : {
		top: padding,
		right: padding,
		bottom: padding,
		left: padding
	};
}
function rectToClientRect(rect) {
	const { x, y, width, height } = rect;
	return {
		width,
		height,
		top: y,
		left: x,
		right: x + width,
		bottom: y + height,
		x,
		y
	};
}
// node_modules/@floating-ui/core/dist/floating-ui.core.mjs
function computeCoordsFromPlacement(_ref, placement, rtl) {
	let { reference, floating } = _ref;
	const sideAxis = getSideAxis(placement);
	const alignmentAxis = getAlignmentAxis(placement);
	const alignLength = getAxisLength(alignmentAxis);
	const side = getSide(placement);
	const isVertical = sideAxis === "y";
	const commonX = reference.x + reference.width / 2 - floating.width / 2;
	const commonY = reference.y + reference.height / 2 - floating.height / 2;
	const commonAlign = reference[alignLength] / 2 - floating[alignLength] / 2;
	let coords;
	switch (side) {
		case "top":
			coords = {
				x: commonX,
				y: reference.y - floating.height
			};
			break;
		case "bottom":
			coords = {
				x: commonX,
				y: reference.y + reference.height
			};
			break;
		case "right":
			coords = {
				x: reference.x + reference.width,
				y: commonY
			};
			break;
		case "left":
			coords = {
				x: reference.x - floating.width,
				y: commonY
			};
			break;
		default: coords = {
			x: reference.x,
			y: reference.y
		};
	}
	const alignment = getAlignment(placement);
	if (alignment) coords[alignmentAxis] += commonAlign * (alignment === "end" ? 1 : -1) * (rtl && isVertical ? -1 : 1);
	return coords;
}
/**
* Resolves with an object of overflow side offsets that determine how much the
* element is overflowing a given clipping boundary on each side.
* - positive = overflowing the boundary by that number of pixels
* - negative = how many pixels left before it will overflow
* - 0 = lies flush with the boundary
* @see https://floating-ui.com/docs/detectOverflow
*/
async function detectOverflow(state, options) {
	var _await$platform$isEle;
	if (options === void 0) options = {};
	const { x, y, platform, rects, elements, strategy } = state;
	const { boundary = "clippingAncestors", rootBoundary = "viewport", elementContext = "floating", altBoundary = false, padding = 0 } = evaluate(options, state);
	const paddingObject = getPaddingObject(padding);
	const element = elements[altBoundary ? elementContext === "floating" ? "reference" : "floating" : elementContext];
	const clippingClientRect = rectToClientRect(await platform.getClippingRect({
		element: ((_await$platform$isEle = await (platform.isElement == null ? void 0 : platform.isElement(element))) != null ? _await$platform$isEle : true) ? element : element.contextElement || await (platform.getDocumentElement == null ? void 0 : platform.getDocumentElement(elements.floating)),
		boundary,
		rootBoundary,
		strategy
	}));
	const rect = elementContext === "floating" ? {
		x,
		y,
		width: rects.floating.width,
		height: rects.floating.height
	} : rects.reference;
	const offsetParent = await (platform.getOffsetParent == null ? void 0 : platform.getOffsetParent(elements.floating));
	const offsetScale = await (platform.isElement == null ? void 0 : platform.isElement(offsetParent)) && await (platform.getScale == null ? void 0 : platform.getScale(offsetParent)) || {
		x: 1,
		y: 1
	};
	const elementClientRect = rectToClientRect(platform.convertOffsetParentRelativeRectToViewportRelativeRect ? await platform.convertOffsetParentRelativeRectToViewportRelativeRect({
		elements,
		rect,
		offsetParent,
		strategy
	}) : rect);
	return {
		top: (clippingClientRect.top - elementClientRect.top + paddingObject.top) / offsetScale.y,
		bottom: (elementClientRect.bottom - clippingClientRect.bottom + paddingObject.bottom) / offsetScale.y,
		left: (clippingClientRect.left - elementClientRect.left + paddingObject.left) / offsetScale.x,
		right: (elementClientRect.right - clippingClientRect.right + paddingObject.right) / offsetScale.x
	};
}
var MAX_RESET_COUNT = 50;
/**
* Computes the `x` and `y` coordinates that will place the floating element
* next to a given reference element.
*
* This export does not have any `platform` interface logic. You will need to
* write one for the platform you are using Floating UI with.
*/
var computePosition$1 = async (reference, floating, config) => {
	const { placement = "bottom", strategy = "absolute", middleware = [], platform } = config;
	const platformWithDetectOverflow = platform.detectOverflow ? platform : {
		...platform,
		detectOverflow
	};
	const rtl = await (platform.isRTL == null ? void 0 : platform.isRTL(floating));
	let rects = await platform.getElementRects({
		reference,
		floating,
		strategy
	});
	let { x, y } = computeCoordsFromPlacement(rects, placement, rtl);
	let statefulPlacement = placement;
	let resetCount = 0;
	const middlewareData = {};
	for (let i = 0; i < middleware.length; i++) {
		const currentMiddleware = middleware[i];
		if (!currentMiddleware) continue;
		const { name, fn } = currentMiddleware;
		const { x: nextX, y: nextY, data, reset } = await fn({
			x,
			y,
			initialPlacement: placement,
			placement: statefulPlacement,
			strategy,
			middlewareData,
			rects,
			platform: platformWithDetectOverflow,
			elements: {
				reference,
				floating
			}
		});
		x = nextX != null ? nextX : x;
		y = nextY != null ? nextY : y;
		middlewareData[name] = {
			...middlewareData[name],
			...data
		};
		if (reset && resetCount < MAX_RESET_COUNT) {
			resetCount++;
			if (typeof reset === "object") {
				if (reset.placement) statefulPlacement = reset.placement;
				if (reset.rects) rects = reset.rects === true ? await platform.getElementRects({
					reference,
					floating,
					strategy
				}) : reset.rects;
				({x, y} = computeCoordsFromPlacement(rects, statefulPlacement, rtl));
			}
			i = -1;
		}
	}
	return {
		x,
		y,
		placement: statefulPlacement,
		strategy,
		middlewareData
	};
};
/**
* Provides data to position an inner element of the floating element so that it
* appears centered to the reference element.
* @see https://floating-ui.com/docs/arrow
*/
var arrow$1 = (options) => ({
	name: "arrow",
	options,
	async fn(state) {
		const { x, y, placement, rects, platform, elements, middlewareData } = state;
		const { element, padding = 0 } = evaluate(options, state) || {};
		if (element == null) return {};
		const paddingObject = getPaddingObject(padding);
		const coords = {
			x,
			y
		};
		const axis = getAlignmentAxis(placement);
		const length = getAxisLength(axis);
		const arrowDimensions = await platform.getDimensions(element);
		const isYAxis = axis === "y";
		const minProp = isYAxis ? "top" : "left";
		const maxProp = isYAxis ? "bottom" : "right";
		const clientProp = isYAxis ? "clientHeight" : "clientWidth";
		const endDiff = rects.reference[length] + rects.reference[axis] - coords[axis] - rects.floating[length];
		const startDiff = coords[axis] - rects.reference[axis];
		const arrowOffsetParent = await (platform.getOffsetParent == null ? void 0 : platform.getOffsetParent(element));
		let clientSize = arrowOffsetParent ? arrowOffsetParent[clientProp] : 0;
		if (!clientSize || !await (platform.isElement == null ? void 0 : platform.isElement(arrowOffsetParent))) clientSize = elements.floating[clientProp] || rects.floating[length];
		const centerToReference = endDiff / 2 - startDiff / 2;
		const largestPossiblePadding = clientSize / 2 - arrowDimensions[length] / 2 - 1;
		const minPadding = min(paddingObject[minProp], largestPossiblePadding);
		const maxPadding = min(paddingObject[maxProp], largestPossiblePadding);
		const max = clientSize - arrowDimensions[length] - maxPadding;
		const center = clientSize / 2 - arrowDimensions[length] / 2 + centerToReference;
		const offset = clamp(minPadding, center, max);
		const shouldAddOffset = !middlewareData.arrow && getAlignment(placement) != null && center !== offset && rects.reference[length] / 2 - (center < minPadding ? minPadding : maxPadding) - arrowDimensions[length] / 2 < 0;
		const alignmentOffset = shouldAddOffset ? center < minPadding ? center - minPadding : center - max : 0;
		return {
			[axis]: coords[axis] + alignmentOffset,
			data: {
				[axis]: offset,
				centerOffset: center - offset - alignmentOffset,
				...shouldAddOffset && { alignmentOffset }
			},
			reset: shouldAddOffset
		};
	}
});
/**
* Optimizes the visibility of the floating element by flipping the `placement`
* in order to keep it in view when the preferred placement(s) will overflow the
* clipping boundary. Alternative to `autoPlacement`.
* @see https://floating-ui.com/docs/flip
*/
var flip$1 = function(options) {
	if (options === void 0) options = {};
	return {
		name: "flip",
		options,
		async fn(state) {
			var _middlewareData$arrow, _middlewareData$flip;
			const { placement, middlewareData, rects, initialPlacement, platform, elements } = state;
			const { mainAxis: checkMainAxis = true, crossAxis: checkCrossAxis = true, fallbackPlacements: specifiedFallbackPlacements, fallbackStrategy = "bestFit", fallbackAxisSideDirection = "none", flipAlignment = true, ...detectOverflowOptions } = evaluate(options, state);
			if ((_middlewareData$arrow = middlewareData.arrow) != null && _middlewareData$arrow.alignmentOffset) return {};
			const side = getSide(placement);
			const initialSideAxis = getSideAxis(initialPlacement);
			const isBasePlacement = getSide(initialPlacement) === initialPlacement;
			const rtl = await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating));
			const fallbackPlacements = specifiedFallbackPlacements || (isBasePlacement || !flipAlignment ? [getOppositePlacement(initialPlacement)] : getExpandedPlacements(initialPlacement));
			const hasFallbackAxisSideDirection = fallbackAxisSideDirection !== "none";
			if (!specifiedFallbackPlacements && hasFallbackAxisSideDirection) fallbackPlacements.push(...getOppositeAxisPlacements(initialPlacement, flipAlignment, fallbackAxisSideDirection, rtl));
			const placements = [initialPlacement, ...fallbackPlacements];
			const overflow = await platform.detectOverflow(state, detectOverflowOptions);
			const overflows = [];
			let overflowsData = ((_middlewareData$flip = middlewareData.flip) == null ? void 0 : _middlewareData$flip.overflows) || [];
			if (checkMainAxis) overflows.push(overflow[side]);
			if (checkCrossAxis) {
				const sides = getAlignmentSides(placement, rects, rtl);
				overflows.push(overflow[sides[0]], overflow[sides[1]]);
			}
			overflowsData = [...overflowsData, {
				placement,
				overflows
			}];
			if (!overflows.every((side) => side <= 0)) {
				var _middlewareData$flip2, _overflowsData$filter;
				const nextIndex = (((_middlewareData$flip2 = middlewareData.flip) == null ? void 0 : _middlewareData$flip2.index) || 0) + 1;
				const nextPlacement = placements[nextIndex];
				if (nextPlacement) {
					if (!(checkCrossAxis === "alignment" ? initialSideAxis !== getSideAxis(nextPlacement) : false) || overflowsData.every((d) => getSideAxis(d.placement) === initialSideAxis ? d.overflows[0] > 0 : true)) return {
						data: {
							index: nextIndex,
							overflows: overflowsData
						},
						reset: { placement: nextPlacement }
					};
				}
				let resetPlacement = (_overflowsData$filter = overflowsData.filter((d) => d.overflows[0] <= 0).sort((a, b) => a.overflows[1] - b.overflows[1])[0]) == null ? void 0 : _overflowsData$filter.placement;
				if (!resetPlacement) switch (fallbackStrategy) {
					case "bestFit": {
						var _overflowsData$filter2;
						const placement = (_overflowsData$filter2 = overflowsData.filter((d) => {
							if (hasFallbackAxisSideDirection) {
								const currentSideAxis = getSideAxis(d.placement);
								return currentSideAxis === initialSideAxis || currentSideAxis === "y";
							}
							return true;
						}).map((d) => [d.placement, d.overflows.filter((overflow) => overflow > 0).reduce((acc, overflow) => acc + overflow, 0)]).sort((a, b) => a[1] - b[1])[0]) == null ? void 0 : _overflowsData$filter2[0];
						if (placement) resetPlacement = placement;
						break;
					}
					case "initialPlacement": resetPlacement = initialPlacement;
				}
				if (placement !== resetPlacement) return { reset: { placement: resetPlacement } };
			}
			return {};
		}
	};
};
var originSides = /*#__PURE__*/ new Set(["left", "top"]);
async function convertValueToCoords(state, options) {
	const { placement, platform, elements } = state;
	const rtl = await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating));
	const side = getSide(placement);
	const alignment = getAlignment(placement);
	const isVertical = getSideAxis(placement) === "y";
	const mainAxisMulti = originSides.has(side) ? -1 : 1;
	const crossAxisMulti = rtl && isVertical ? -1 : 1;
	const rawValue = evaluate(options, state);
	let { mainAxis, crossAxis, alignmentAxis } = typeof rawValue === "number" ? {
		mainAxis: rawValue,
		crossAxis: 0,
		alignmentAxis: null
	} : {
		mainAxis: rawValue.mainAxis || 0,
		crossAxis: rawValue.crossAxis || 0,
		alignmentAxis: rawValue.alignmentAxis
	};
	if (alignment && typeof alignmentAxis === "number") crossAxis = alignment === "end" ? alignmentAxis * -1 : alignmentAxis;
	return isVertical ? {
		x: crossAxis * crossAxisMulti,
		y: mainAxis * mainAxisMulti
	} : {
		x: mainAxis * mainAxisMulti,
		y: crossAxis * crossAxisMulti
	};
}
/**
* Modifies the placement by translating the floating element along the
* specified axes.
* A number (shorthand for `mainAxis` or distance), or an axes configuration
* object may be passed.
* @see https://floating-ui.com/docs/offset
*/
var offset$1 = function(options) {
	if (options === void 0) options = 0;
	return {
		name: "offset",
		options,
		async fn(state) {
			var _middlewareData$offse, _middlewareData$arrow;
			const { x, y, placement, middlewareData } = state;
			const diffCoords = await convertValueToCoords(state, options);
			if (placement === ((_middlewareData$offse = middlewareData.offset) == null ? void 0 : _middlewareData$offse.placement) && (_middlewareData$arrow = middlewareData.arrow) != null && _middlewareData$arrow.alignmentOffset) return {};
			return {
				x: x + diffCoords.x,
				y: y + diffCoords.y,
				data: {
					...diffCoords,
					placement
				}
			};
		}
	};
};
/**
* Optimizes the visibility of the floating element by shifting it in order to
* keep it in view when it will overflow the clipping boundary.
* @see https://floating-ui.com/docs/shift
*/
var shift$1 = function(options) {
	if (options === void 0) options = {};
	return {
		name: "shift",
		options,
		async fn(state) {
			const { x, y, placement, platform } = state;
			const { mainAxis: checkMainAxis = true, crossAxis: checkCrossAxis = false, limiter = { fn: (_ref) => {
				let { x, y } = _ref;
				return {
					x,
					y
				};
			} }, ...detectOverflowOptions } = evaluate(options, state);
			const coords = {
				x,
				y
			};
			const overflow = await platform.detectOverflow(state, detectOverflowOptions);
			const crossAxis = getSideAxis(placement);
			const mainAxis = getOppositeAxis(crossAxis);
			let mainAxisCoord = coords[mainAxis];
			let crossAxisCoord = coords[crossAxis];
			const clampCoord = (axis, coord) => clamp(coord + overflow[axis === "y" ? "top" : "left"], coord, coord - overflow[axis === "y" ? "bottom" : "right"]);
			if (checkMainAxis) mainAxisCoord = clampCoord(mainAxis, mainAxisCoord);
			if (checkCrossAxis) crossAxisCoord = clampCoord(crossAxis, crossAxisCoord);
			const limitedCoords = limiter.fn({
				...state,
				[mainAxis]: mainAxisCoord,
				[crossAxis]: crossAxisCoord
			});
			return {
				...limitedCoords,
				data: {
					x: limitedCoords.x - x,
					y: limitedCoords.y - y,
					enabled: {
						[mainAxis]: checkMainAxis,
						[crossAxis]: checkCrossAxis
					}
				}
			};
		}
	};
};
/**
* Provides data that allows you to change the size of the floating element —
* for instance, prevent it from overflowing the clipping boundary or match the
* width of the reference element.
* @see https://floating-ui.com/docs/size
*/
var size$1 = function(options) {
	if (options === void 0) options = {};
	return {
		name: "size",
		options,
		async fn(state) {
			const { placement, rects, platform, elements } = state;
			const { apply = () => {}, ...detectOverflowOptions } = evaluate(options, state);
			const overflow = await platform.detectOverflow(state, detectOverflowOptions);
			const side = getSide(placement);
			const alignment = getAlignment(placement);
			const isYAxis = getSideAxis(placement) === "y";
			const { width, height } = rects.floating;
			let heightSide;
			let widthSide;
			if (side === "top" || side === "bottom") {
				heightSide = side;
				widthSide = alignment === (await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating)) ? "start" : "end") ? "left" : "right";
			} else {
				widthSide = side;
				heightSide = alignment === "end" ? "top" : "bottom";
			}
			const maximumClippingHeight = height - overflow.top - overflow.bottom;
			const maximumClippingWidth = width - overflow.left - overflow.right;
			const overflowAvailableHeight = min(height - overflow[heightSide], maximumClippingHeight);
			const overflowAvailableWidth = min(width - overflow[widthSide], maximumClippingWidth);
			const shiftData = state.middlewareData.shift;
			const noShift = !shiftData;
			let availableHeight = overflowAvailableHeight;
			let availableWidth = overflowAvailableWidth;
			if (shiftData != null && shiftData.enabled.x) availableWidth = maximumClippingWidth;
			if (shiftData != null && shiftData.enabled.y) availableHeight = maximumClippingHeight;
			if (noShift && !alignment) {
				if (isYAxis) availableWidth = width - 2 * max(overflow.left, overflow.right);
				else availableHeight = height - 2 * max(overflow.top, overflow.bottom);
			}
			await apply({
				...state,
				availableWidth,
				availableHeight
			});
			const nextDimensions = await platform.getDimensions(elements.floating);
			if (width !== nextDimensions.width || height !== nextDimensions.height) return { reset: { rects: true } };
			return {};
		}
	};
};
// node_modules/@floating-ui/utils/dist/floating-ui.utils.dom.mjs
function hasWindow() {
	return typeof window !== "undefined";
}
function getNodeName(node) {
	if (isNode(node)) return (node.nodeName || "").toLowerCase();
	return "#document";
}
function getWindow(node) {
	var _node$ownerDocument;
	return (node == null || (_node$ownerDocument = node.ownerDocument) == null ? void 0 : _node$ownerDocument.defaultView) || window;
}
function getDocumentElement(node) {
	var _ref;
	return (_ref = (isNode(node) ? node.ownerDocument : node.document) || window.document) == null ? void 0 : _ref.documentElement;
}
function isNode(value) {
	if (!hasWindow()) return false;
	return value instanceof Node || value instanceof getWindow(value).Node;
}
function isElement(value) {
	if (!hasWindow()) return false;
	return value instanceof Element || value instanceof getWindow(value).Element;
}
function isHTMLElement(value) {
	if (!hasWindow()) return false;
	return value instanceof HTMLElement || value instanceof getWindow(value).HTMLElement;
}
function isShadowRoot(value) {
	if (!hasWindow() || typeof ShadowRoot === "undefined") return false;
	return value instanceof ShadowRoot || value instanceof getWindow(value).ShadowRoot;
}
function isOverflowElement(element) {
	const { overflow, overflowX, overflowY, display } = getComputedStyle$1(element);
	return /auto|scroll|overlay|hidden|clip/.test(overflow + overflowY + overflowX) && display !== "inline" && display !== "contents";
}
function isTableElement(element) {
	return /^(table|td|th)$/.test(getNodeName(element));
}
function isTopLayer(element) {
	try {
		if (element.matches(":popover-open")) return true;
	} catch (_e) {}
	try {
		return element.matches(":modal");
	} catch (_e) {
		return false;
	}
}
var willChangeRe = /transform|translate|scale|rotate|perspective|filter/;
var containRe = /paint|layout|strict|content/;
var isNotNone = (value) => !!value && value !== "none";
var isWebKitValue;
function isContainingBlock(elementOrCss) {
	const css = isElement(elementOrCss) ? getComputedStyle$1(elementOrCss) : elementOrCss;
	return isNotNone(css.transform) || isNotNone(css.translate) || isNotNone(css.scale) || isNotNone(css.rotate) || isNotNone(css.perspective) || !isWebKit() && (isNotNone(css.backdropFilter) || isNotNone(css.filter)) || willChangeRe.test(css.willChange || "") || containRe.test(css.contain || "");
}
function getContainingBlock(element) {
	let currentNode = getParentNode(element);
	while (isHTMLElement(currentNode) && !isLastTraversableNode(currentNode)) {
		if (isContainingBlock(currentNode)) return currentNode;
		else if (isTopLayer(currentNode)) return null;
		currentNode = getParentNode(currentNode);
	}
	return null;
}
function isWebKit() {
	if (isWebKitValue == null) isWebKitValue = typeof CSS !== "undefined" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none");
	return isWebKitValue;
}
function isLastTraversableNode(node) {
	return /^(html|body|#document)$/.test(getNodeName(node));
}
function getComputedStyle$1(element) {
	return getWindow(element).getComputedStyle(element);
}
function getNodeScroll(element) {
	if (isElement(element)) return {
		scrollLeft: element.scrollLeft,
		scrollTop: element.scrollTop
	};
	return {
		scrollLeft: element.scrollX,
		scrollTop: element.scrollY
	};
}
function getParentNode(node) {
	if (getNodeName(node) === "html") return node;
	const result = node.assignedSlot || node.parentNode || isShadowRoot(node) && node.host || getDocumentElement(node);
	return isShadowRoot(result) ? result.host : result;
}
function getNearestOverflowAncestor(node) {
	const parentNode = getParentNode(node);
	if (isLastTraversableNode(parentNode)) return (node.ownerDocument || node).body;
	if (isHTMLElement(parentNode) && isOverflowElement(parentNode)) return parentNode;
	return getNearestOverflowAncestor(parentNode);
}
function getOverflowAncestors(node, list, traverseIframes) {
	var _node$ownerDocument2;
	if (list === void 0) list = [];
	if (traverseIframes === void 0) traverseIframes = true;
	const scrollableAncestor = getNearestOverflowAncestor(node);
	const isBody = scrollableAncestor === ((_node$ownerDocument2 = node.ownerDocument) == null ? void 0 : _node$ownerDocument2.body);
	const win = getWindow(scrollableAncestor);
	if (isBody) {
		const frameElement = getFrameElement(win);
		return list.concat(win, win.visualViewport || [], isOverflowElement(scrollableAncestor) ? scrollableAncestor : [], frameElement && traverseIframes ? getOverflowAncestors(frameElement) : []);
	} else return list.concat(scrollableAncestor, getOverflowAncestors(scrollableAncestor, [], traverseIframes));
}
function getFrameElement(win) {
	return win.parent && Object.getPrototypeOf(win.parent) ? win.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function getCssDimensions(element) {
	const css = getComputedStyle$1(element);
	let width = parseFloat(css.width) || 0;
	let height = parseFloat(css.height) || 0;
	const hasOffset = isHTMLElement(element);
	const offsetWidth = hasOffset ? element.offsetWidth : width;
	const offsetHeight = hasOffset ? element.offsetHeight : height;
	const shouldFallback = round(width) !== offsetWidth || round(height) !== offsetHeight;
	if (shouldFallback) {
		width = offsetWidth;
		height = offsetHeight;
	}
	return {
		width,
		height,
		$: shouldFallback
	};
}
function unwrapElement(element) {
	return !isElement(element) ? element.contextElement : element;
}
function getScale(element) {
	const domElement = unwrapElement(element);
	if (!isHTMLElement(domElement)) return createCoords(1);
	const rect = domElement.getBoundingClientRect();
	const { width, height, $ } = getCssDimensions(domElement);
	let x = ($ ? round(rect.width) : rect.width) / width;
	let y = ($ ? round(rect.height) : rect.height) / height;
	if (!x || !Number.isFinite(x)) x = 1;
	if (!y || !Number.isFinite(y)) y = 1;
	return {
		x,
		y
	};
}
var noOffsets = /*#__PURE__*/ createCoords(0);
function getVisualOffsets(element) {
	const win = getWindow(element);
	if (!isWebKit() || !win.visualViewport) return noOffsets;
	return {
		x: win.visualViewport.offsetLeft,
		y: win.visualViewport.offsetTop
	};
}
function shouldAddVisualOffsets(element, isFixed, floatingOffsetParent) {
	if (isFixed === void 0) isFixed = false;
	return !!floatingOffsetParent && isFixed && floatingOffsetParent === getWindow(element);
}
function getBoundingClientRect(element, includeScale, isFixedStrategy, offsetParent) {
	if (includeScale === void 0) includeScale = false;
	if (isFixedStrategy === void 0) isFixedStrategy = false;
	const clientRect = element.getBoundingClientRect();
	const domElement = unwrapElement(element);
	let scale = createCoords(1);
	if (includeScale) {
		if (offsetParent) {
			if (isElement(offsetParent)) scale = getScale(offsetParent);
		} else scale = getScale(element);
	}
	const visualOffsets = shouldAddVisualOffsets(domElement, isFixedStrategy, offsetParent) ? getVisualOffsets(domElement) : createCoords(0);
	let x = (clientRect.left + visualOffsets.x) / scale.x;
	let y = (clientRect.top + visualOffsets.y) / scale.y;
	let width = clientRect.width / scale.x;
	let height = clientRect.height / scale.y;
	if (domElement && offsetParent) {
		const win = getWindow(domElement);
		const offsetWin = isElement(offsetParent) ? getWindow(offsetParent) : offsetParent;
		let currentWin = win;
		let currentIFrame = getFrameElement(currentWin);
		while (currentIFrame && offsetWin !== currentWin) {
			const iframeScale = getScale(currentIFrame);
			const iframeRect = currentIFrame.getBoundingClientRect();
			const css = getComputedStyle$1(currentIFrame);
			const left = iframeRect.left + (currentIFrame.clientLeft + parseFloat(css.paddingLeft)) * iframeScale.x;
			const top = iframeRect.top + (currentIFrame.clientTop + parseFloat(css.paddingTop)) * iframeScale.y;
			x *= iframeScale.x;
			y *= iframeScale.y;
			width *= iframeScale.x;
			height *= iframeScale.y;
			x += left;
			y += top;
			currentWin = getWindow(currentIFrame);
			currentIFrame = getFrameElement(currentWin);
		}
	}
	return rectToClientRect({
		width,
		height,
		x,
		y
	});
}
function getWindowScrollBarX(element, rect) {
	const leftScroll = getNodeScroll(element).scrollLeft;
	if (!rect) return getBoundingClientRect(getDocumentElement(element)).left + leftScroll;
	return rect.left + leftScroll;
}
function getHTMLOffset(documentElement, scroll) {
	const htmlRect = documentElement.getBoundingClientRect();
	return {
		x: htmlRect.left + scroll.scrollLeft - getWindowScrollBarX(documentElement, htmlRect),
		y: htmlRect.top + scroll.scrollTop
	};
}
function convertOffsetParentRelativeRectToViewportRelativeRect(_ref) {
	let { elements, rect, offsetParent, strategy } = _ref;
	const isFixed = strategy === "fixed";
	const documentElement = getDocumentElement(offsetParent);
	const topLayer = elements ? isTopLayer(elements.floating) : false;
	if (offsetParent === documentElement || topLayer && isFixed) return rect;
	let scroll = {
		scrollLeft: 0,
		scrollTop: 0
	};
	let scale = createCoords(1);
	const offsets = createCoords(0);
	const isOffsetParentAnElement = isHTMLElement(offsetParent);
	if (isOffsetParentAnElement || !isFixed) {
		if (getNodeName(offsetParent) !== "body" || isOverflowElement(documentElement)) scroll = getNodeScroll(offsetParent);
		if (isOffsetParentAnElement) {
			const offsetRect = getBoundingClientRect(offsetParent);
			scale = getScale(offsetParent);
			offsets.x = offsetRect.x + offsetParent.clientLeft;
			offsets.y = offsetRect.y + offsetParent.clientTop;
		}
	}
	const htmlOffset = documentElement && !isOffsetParentAnElement && !isFixed ? getHTMLOffset(documentElement, scroll) : createCoords(0);
	return {
		width: rect.width * scale.x,
		height: rect.height * scale.y,
		x: rect.x * scale.x - scroll.scrollLeft * scale.x + offsets.x + htmlOffset.x,
		y: rect.y * scale.y - scroll.scrollTop * scale.y + offsets.y + htmlOffset.y
	};
}
function getClientRects(element) {
	return element.getClientRects ? Array.from(element.getClientRects()) : [];
}
function getDocumentRect(html) {
	const scroll = getNodeScroll(html);
	const body = html.ownerDocument.body;
	const width = max(html.scrollWidth, html.clientWidth, body.scrollWidth, body.clientWidth);
	const height = max(html.scrollHeight, html.clientHeight, body.scrollHeight, body.clientHeight);
	let x = -scroll.scrollLeft + getWindowScrollBarX(html);
	const y = -scroll.scrollTop;
	if (getComputedStyle$1(body).direction === "rtl") x += max(html.clientWidth, body.clientWidth) - width;
	return {
		width,
		height,
		x,
		y
	};
}
var SCROLLBAR_MAX = 25;
function getViewportRect(element, strategy, rootBoundary) {
	if (rootBoundary === void 0) rootBoundary = "viewport";
	const isLayoutViewport = rootBoundary === "layoutViewport";
	const win = getWindow(element);
	const html = getDocumentElement(element);
	const visualViewport = win.visualViewport;
	let width = html.clientWidth;
	let height = html.clientHeight;
	let x = 0;
	let y = 0;
	if (visualViewport) {
		const layoutRelativeClientCoords = !isWebKit() || strategy === "fixed";
		if (isLayoutViewport) {
			if (!layoutRelativeClientCoords) {
				x = -visualViewport.offsetLeft;
				y = -visualViewport.offsetTop;
			}
		} else {
			width = visualViewport.width;
			height = visualViewport.height;
			if (layoutRelativeClientCoords) {
				x = visualViewport.offsetLeft;
				y = visualViewport.offsetTop;
			}
		}
	}
	if (getWindowScrollBarX(html) <= 0) {
		const doc = html.ownerDocument;
		const body = doc.body;
		const bodyStyles = getComputedStyle(body);
		const bodyMarginInline = doc.compatMode === "CSS1Compat" ? parseFloat(bodyStyles.marginLeft) + parseFloat(bodyStyles.marginRight) || 0 : 0;
		const reservedWidth = Math.abs(html.clientWidth - body.clientWidth - bodyMarginInline);
		const gutter = getComputedStyle(html).scrollbarGutter === "stable both-edges" ? reservedWidth / 2 : reservedWidth;
		if (gutter <= SCROLLBAR_MAX) width -= gutter;
	}
	return {
		width,
		height,
		x,
		y
	};
}
function getInnerBoundingClientRect(element, strategy) {
	const clientRect = getBoundingClientRect(element, true, strategy === "fixed");
	const top = clientRect.top + element.clientTop;
	const left = clientRect.left + element.clientLeft;
	const scale = getScale(element);
	return {
		width: element.clientWidth * scale.x,
		height: element.clientHeight * scale.y,
		x: left * scale.x,
		y: top * scale.y
	};
}
function getClientRectFromClippingAncestor(element, clippingAncestor, strategy) {
	let rect;
	if (clippingAncestor === "viewport" || clippingAncestor === "layoutViewport") rect = getViewportRect(element, strategy, clippingAncestor);
	else if (clippingAncestor === "document") rect = getDocumentRect(getDocumentElement(element));
	else if (isElement(clippingAncestor)) rect = getInnerBoundingClientRect(clippingAncestor, strategy);
	else {
		const visualOffsets = getVisualOffsets(element);
		rect = {
			x: clippingAncestor.x - visualOffsets.x,
			y: clippingAncestor.y - visualOffsets.y,
			width: clippingAncestor.width,
			height: clippingAncestor.height
		};
	}
	return rectToClientRect(rect);
}
function getClippingElementAncestors(element, cache) {
	const cachedResult = cache.get(element);
	if (cachedResult) return cachedResult;
	let result = getOverflowAncestors(element, [], false).filter((el) => isElement(el) && getNodeName(el) !== "body");
	let lastKeptComputedStyle = null;
	const elementIsFixed = getComputedStyle$1(element).position === "fixed";
	let currentNode = elementIsFixed ? getParentNode(element) : element;
	while (isElement(currentNode) && !isLastTraversableNode(currentNode)) {
		const computedStyle = getComputedStyle$1(currentNode);
		const currentNodeIsContaining = isContainingBlock(currentNode);
		const lastPosition = lastKeptComputedStyle ? lastKeptComputedStyle.position : elementIsFixed ? "fixed" : "";
		if (!currentNodeIsContaining && (lastPosition === "fixed" || lastPosition === "absolute" && computedStyle.position === "static")) result = result.filter((ancestor) => ancestor !== currentNode);
		else lastKeptComputedStyle = computedStyle;
		currentNode = getParentNode(currentNode);
	}
	cache.set(element, result);
	return result;
}
function getClippingRect(_ref) {
	let { element, boundary, rootBoundary, strategy } = _ref;
	const clippingAncestors = [...boundary === "clippingAncestors" ? isTopLayer(element) ? [] : getClippingElementAncestors(element, this._c) : [].concat(boundary), rootBoundary];
	const firstRect = getClientRectFromClippingAncestor(element, clippingAncestors[0], strategy);
	let top = firstRect.top;
	let right = firstRect.right;
	let bottom = firstRect.bottom;
	let left = firstRect.left;
	for (let i = 1; i < clippingAncestors.length; i++) {
		const rect = getClientRectFromClippingAncestor(element, clippingAncestors[i], strategy);
		top = max(rect.top, top);
		right = min(rect.right, right);
		bottom = min(rect.bottom, bottom);
		left = max(rect.left, left);
	}
	return {
		width: right - left,
		height: bottom - top,
		x: left,
		y: top
	};
}
function getDimensions(element) {
	const { width, height } = getCssDimensions(element);
	return {
		width,
		height
	};
}
function getRectRelativeToOffsetParent(element, offsetParent, strategy) {
	const isOffsetParentAnElement = isHTMLElement(offsetParent);
	const documentElement = getDocumentElement(offsetParent);
	const isFixed = strategy === "fixed";
	const rect = getBoundingClientRect(element, true, isFixed, offsetParent);
	let scroll = {
		scrollLeft: 0,
		scrollTop: 0
	};
	const offsets = createCoords(0);
	if (isOffsetParentAnElement || !isFixed) {
		if (getNodeName(offsetParent) !== "body" || isOverflowElement(documentElement)) scroll = getNodeScroll(offsetParent);
		if (isOffsetParentAnElement) {
			const offsetRect = getBoundingClientRect(offsetParent, true, isFixed, offsetParent);
			offsets.x = offsetRect.x + offsetParent.clientLeft;
			offsets.y = offsetRect.y + offsetParent.clientTop;
		}
	}
	if (!isOffsetParentAnElement && documentElement) offsets.x = getWindowScrollBarX(documentElement);
	const htmlOffset = documentElement && !isOffsetParentAnElement && !isFixed ? getHTMLOffset(documentElement, scroll) : createCoords(0);
	return {
		x: rect.left + scroll.scrollLeft - offsets.x - htmlOffset.x,
		y: rect.top + scroll.scrollTop - offsets.y - htmlOffset.y,
		width: rect.width,
		height: rect.height
	};
}
function isStaticPositioned(element) {
	return getComputedStyle$1(element).position === "static";
}
function getTrueOffsetParent(element, polyfill) {
	if (!isHTMLElement(element) || getComputedStyle$1(element).position === "fixed") return null;
	if (polyfill) return polyfill(element);
	let rawOffsetParent = element.offsetParent;
	if (getDocumentElement(element) === rawOffsetParent) rawOffsetParent = rawOffsetParent.ownerDocument.body;
	return rawOffsetParent;
}
function getOffsetParent(element, polyfill) {
	const win = getWindow(element);
	if (isTopLayer(element)) return win;
	if (!isHTMLElement(element)) {
		let svgOffsetParent = getParentNode(element);
		while (svgOffsetParent && !isLastTraversableNode(svgOffsetParent)) {
			if (isElement(svgOffsetParent) && !isStaticPositioned(svgOffsetParent)) return svgOffsetParent;
			svgOffsetParent = getParentNode(svgOffsetParent);
		}
		return win;
	}
	let offsetParent = getTrueOffsetParent(element, polyfill);
	while (offsetParent && isTableElement(offsetParent) && isStaticPositioned(offsetParent)) offsetParent = getTrueOffsetParent(offsetParent, polyfill);
	if (offsetParent && isLastTraversableNode(offsetParent) && isStaticPositioned(offsetParent) && !isContainingBlock(offsetParent)) return win;
	return offsetParent || getContainingBlock(element) || win;
}
var getElementRects = async function(data) {
	const getOffsetParentFn = this.getOffsetParent || getOffsetParent;
	const getDimensionsFn = this.getDimensions;
	const floatingDimensions = await getDimensionsFn(data.floating);
	return {
		reference: getRectRelativeToOffsetParent(data.reference, await getOffsetParentFn(data.floating), data.strategy),
		floating: {
			x: 0,
			y: 0,
			width: floatingDimensions.width,
			height: floatingDimensions.height
		}
	};
};
function isRTL(element) {
	return getComputedStyle$1(element).direction === "rtl";
}
var platform = {
	convertOffsetParentRelativeRectToViewportRelativeRect,
	getDocumentElement,
	getClippingRect,
	getOffsetParent,
	getElementRects,
	getClientRects,
	getDimensions,
	getScale,
	isElement,
	isRTL
};
function rectsAreEqual(a, b) {
	return a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height;
}
function observeMove(element, onMove, ancestorResize) {
	let io = null;
	let timeoutId;
	const root = getDocumentElement(element);
	function cleanup() {
		var _io;
		clearTimeout(timeoutId);
		(_io = io) == null || _io.disconnect();
		io = null;
	}
	function refresh(skip, threshold) {
		if (skip === void 0) skip = false;
		if (threshold === void 0) threshold = 1;
		cleanup();
		const elementRectForRootMargin = element.getBoundingClientRect();
		const { left, top, width, height } = elementRectForRootMargin;
		if (!skip) onMove();
		if (!width || !height) return;
		const insetTop = floor(top);
		const insetRight = floor(root.clientWidth - (left + width));
		const insetBottom = floor(root.clientHeight - (top + height));
		const insetLeft = floor(left);
		const options = {
			rootMargin: -insetTop + "px " + -insetRight + "px " + -insetBottom + "px " + -insetLeft + "px",
			threshold: max(0, min(1, threshold)) || 1
		};
		let isFirstUpdate = true;
		function handleObserve(entries) {
			const ratio = entries[0].intersectionRatio;
			if (!rectsAreEqual(elementRectForRootMargin, element.getBoundingClientRect())) return refresh();
			if (ratio !== threshold) {
				if (!isFirstUpdate) return refresh();
				if (!ratio) timeoutId = setTimeout(() => {
					refresh(false, 1e-7);
				}, 1e3);
				else refresh(false, ratio);
			}
			isFirstUpdate = false;
		}
		try {
			io = new IntersectionObserver(handleObserve, {
				...options,
				root: root.ownerDocument
			});
		} catch (_e) {
			io = new IntersectionObserver(handleObserve, options);
		}
		io.observe(element);
	}
	const win = getWindow(element);
	const handleResize = () => refresh(ancestorResize);
	win.addEventListener("resize", handleResize);
	refresh(true);
	return () => {
		win.removeEventListener("resize", handleResize);
		cleanup();
	};
}
/**
* Automatically updates the position of the floating element when necessary.
* Should only be called when the floating element is mounted on the DOM or
* visible on the screen.
* @returns cleanup function that should be invoked when the floating element is
* removed from the DOM or hidden from the screen.
* @see https://floating-ui.com/docs/autoUpdate
*/
function autoUpdate(reference, floating, update, options) {
	if (options === void 0) options = {};
	const { ancestorScroll = true, ancestorResize = true, elementResize = typeof ResizeObserver === "function", layoutShift = typeof IntersectionObserver === "function", animationFrame = false } = options;
	const referenceEl = unwrapElement(reference);
	const ancestors = ancestorScroll || ancestorResize ? [...referenceEl ? getOverflowAncestors(referenceEl) : [], ...floating ? getOverflowAncestors(floating) : []] : [];
	ancestors.forEach((ancestor) => {
		ancestorScroll && ancestor.addEventListener("scroll", update);
		ancestorResize && ancestor.addEventListener("resize", update);
	});
	const cleanupIo = referenceEl && layoutShift ? observeMove(referenceEl, update, ancestorResize) : null;
	let reobserveFrame = -1;
	let resizeObserver = null;
	if (elementResize) {
		resizeObserver = new ResizeObserver((_ref) => {
			let [firstEntry] = _ref;
			if (firstEntry && firstEntry.target === referenceEl && resizeObserver && floating) {
				resizeObserver.unobserve(floating);
				cancelAnimationFrame(reobserveFrame);
				reobserveFrame = requestAnimationFrame(() => {
					var _resizeObserver;
					(_resizeObserver = resizeObserver) == null || _resizeObserver.observe(floating);
				});
			}
			update();
		});
		if (referenceEl && !animationFrame) resizeObserver.observe(referenceEl);
		if (floating) resizeObserver.observe(floating);
	}
	let frameId;
	let prevRefRect = animationFrame ? getBoundingClientRect(reference) : null;
	if (animationFrame) frameLoop();
	function frameLoop() {
		const nextRefRect = getBoundingClientRect(reference);
		if (prevRefRect && !rectsAreEqual(prevRefRect, nextRefRect)) update();
		prevRefRect = nextRefRect;
		frameId = requestAnimationFrame(frameLoop);
	}
	update();
	return () => {
		var _resizeObserver2;
		ancestors.forEach((ancestor) => {
			ancestorScroll && ancestor.removeEventListener("scroll", update);
			ancestorResize && ancestor.removeEventListener("resize", update);
		});
		cleanupIo?.();
		(_resizeObserver2 = resizeObserver) == null || _resizeObserver2.disconnect();
		resizeObserver = null;
		if (animationFrame) cancelAnimationFrame(frameId);
	};
}
/**
* Modifies the placement by translating the floating element along the
* specified axes.
* A number (shorthand for `mainAxis` or distance), or an axes configuration
* object may be passed.
* @see https://floating-ui.com/docs/offset
*/
var offset = offset$1;
/**
* Optimizes the visibility of the floating element by shifting it in order to
* keep it in view when it will overflow the clipping boundary.
* @see https://floating-ui.com/docs/shift
*/
var shift = shift$1;
/**
* Optimizes the visibility of the floating element by flipping the `placement`
* in order to keep it in view when the preferred placement(s) will overflow the
* clipping boundary. Alternative to `autoPlacement`.
* @see https://floating-ui.com/docs/flip
*/
var flip = flip$1;
/**
* Provides data that allows you to change the size of the floating element —
* for instance, prevent it from overflowing the clipping boundary or match the
* width of the reference element.
* @see https://floating-ui.com/docs/size
*/
var size = size$1;
/**
* Provides data to position an inner element of the floating element so that it
* appears centered to the reference element.
* @see https://floating-ui.com/docs/arrow
*/
var arrow = arrow$1;
/**
* Computes the `x` and `y` coordinates that will place the floating element
* next to a given reference element.
*/
var computePosition = (reference, floating, options) => {
	const cache = /* @__PURE__ */ new Map();
	const mergedOptions = options != null ? options : {};
	const platformWithCache = {
		...platform,
		...mergedOptions.platform,
		_c: cache
	};
	return computePosition$1(reference, floating, {
		...mergedOptions,
		platform: platformWithCache
	});
};
// node_modules/composed-offset-position/dist/composed-offset-position.browser.min.mjs
function e(t) {
	return i(t);
}
function r(t) {
	return t.assignedSlot ? t.assignedSlot : t.parentNode instanceof ShadowRoot ? t.parentNode.host : t.parentNode;
}
function i(e) {
	for (let t = e; t; t = r(t)) if (t instanceof Element && "none" === getComputedStyle(t).display) return null;
	for (let n = r(e); n; n = r(n)) {
		if (!(n instanceof Element)) continue;
		const e = getComputedStyle(n);
		if ("contents" !== e.display) {
			if ("static" !== e.position || isContainingBlock(e)) return n;
			if ("BODY" === n.tagName) return n;
		}
	}
	return null;
}
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.DC6YZU3I.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function isVirtualElement(e) {
	return e !== null && typeof e === "object" && "getBoundingClientRect" in e && ("contextElement" in e ? e instanceof Element : true);
}
var SUPPORTS_POPOVER = Boolean(globalThis?.HTMLElement?.prototype.hasOwnProperty("popover"));
var WaPopup = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.localize = new LocalizeController(this);
		this.SUPPORTS_POPOVER = false;
		this.active = false;
		this.placement = "top";
		this.boundary = "viewport";
		this.distance = 0;
		this.skidding = 0;
		this.arrow = false;
		this.arrowPlacement = "anchor";
		this.arrowPadding = 10;
		this.flip = false;
		this.flipFallbackPlacements = "";
		this.flipFallbackStrategy = "best-fit";
		this.flipPadding = 0;
		this.shift = false;
		this.shiftPadding = 0;
		this.autoSizePadding = 0;
		this.hoverBridge = false;
		this.updateHoverBridge = () => {
			if (this.hoverBridge && this.anchorEl && this.popup) {
				const anchorRect = this.anchorEl.getBoundingClientRect();
				const popupRect = this.popup.getBoundingClientRect();
				const isVertical = this.placement.includes("top") || this.placement.includes("bottom");
				let topLeftX = 0;
				let topLeftY = 0;
				let topRightX = 0;
				let topRightY = 0;
				let bottomLeftX = 0;
				let bottomLeftY = 0;
				let bottomRightX = 0;
				let bottomRightY = 0;
				if (isVertical) {
					if (anchorRect.top < popupRect.top) {
						topLeftX = anchorRect.left;
						topLeftY = anchorRect.bottom;
						topRightX = anchorRect.right;
						topRightY = anchorRect.bottom;
						bottomLeftX = popupRect.left;
						bottomLeftY = popupRect.top;
						bottomRightX = popupRect.right;
						bottomRightY = popupRect.top;
					} else {
						topLeftX = popupRect.left;
						topLeftY = popupRect.bottom;
						topRightX = popupRect.right;
						topRightY = popupRect.bottom;
						bottomLeftX = anchorRect.left;
						bottomLeftY = anchorRect.top;
						bottomRightX = anchorRect.right;
						bottomRightY = anchorRect.top;
					}
				} else if (anchorRect.left < popupRect.left) {
					topLeftX = anchorRect.right;
					topLeftY = anchorRect.top;
					topRightX = popupRect.left;
					topRightY = popupRect.top;
					bottomLeftX = anchorRect.right;
					bottomLeftY = anchorRect.bottom;
					bottomRightX = popupRect.left;
					bottomRightY = popupRect.bottom;
				} else {
					topLeftX = popupRect.right;
					topLeftY = popupRect.top;
					topRightX = anchorRect.left;
					topRightY = anchorRect.top;
					bottomLeftX = popupRect.right;
					bottomLeftY = popupRect.bottom;
					bottomRightX = anchorRect.left;
					bottomRightY = anchorRect.bottom;
				}
				this.style.setProperty("--hover-bridge-top-left-x", `${topLeftX}px`);
				this.style.setProperty("--hover-bridge-top-left-y", `${topLeftY}px`);
				this.style.setProperty("--hover-bridge-top-right-x", `${topRightX}px`);
				this.style.setProperty("--hover-bridge-top-right-y", `${topRightY}px`);
				this.style.setProperty("--hover-bridge-bottom-left-x", `${bottomLeftX}px`);
				this.style.setProperty("--hover-bridge-bottom-left-y", `${bottomLeftY}px`);
				this.style.setProperty("--hover-bridge-bottom-right-x", `${bottomRightX}px`);
				this.style.setProperty("--hover-bridge-bottom-right-y", `${bottomRightY}px`);
			}
		};
	}
	async connectedCallback() {
		super.connectedCallback();
		await this.updateComplete;
		this.SUPPORTS_POPOVER = SUPPORTS_POPOVER;
		this.start();
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		this.stop();
	}
	async updated(changedProperties) {
		super.updated(changedProperties);
		if (changedProperties.has("active")) {
			if (this.active) this.start();
			else this.stop();
		}
		if (changedProperties.has("anchor")) this.handleAnchorChange();
		if (this.active) {
			await this.updateComplete;
			this.reposition();
		}
	}
	async handleAnchorChange() {
		await this.stop();
		if (this.anchor && typeof this.anchor === "string") {
			const root = this.getRootNode();
			this.anchorEl = root.getElementById(this.anchor);
		} else if (this.anchor instanceof Element || isVirtualElement(this.anchor)) this.anchorEl = this.anchor;
		else this.anchorEl = this.querySelector("[slot=\"anchor\"]");
		if (this.anchorEl instanceof HTMLSlotElement) this.anchorEl = this.anchorEl.assignedElements({ flatten: true })[0];
		if (this.anchorEl) this.start();
	}
	start() {
		if (!this.anchorEl || !this.active || !this.isConnected) return;
		this.cleanup?.();
		this.cleanup = void 0;
		this.popup?.showPopover?.();
		const cleanup = autoUpdate(this.anchorEl, this.popup, () => {
			this.reposition();
		});
		if (!this.active || !this.isConnected) {
			cleanup();
			return;
		}
		this.cleanup = cleanup;
	}
	async stop() {
		return new Promise((resolve) => {
			this.popup?.hidePopover?.();
			if (this.cleanup) {
				this.cleanup();
				this.cleanup = void 0;
				this.removeAttribute("data-current-placement");
				this.style.removeProperty("--auto-size-available-width");
				this.style.removeProperty("--auto-size-available-height");
				requestAnimationFrame(() => resolve());
			} else resolve();
		});
	}
	/** Forces the popup to recalculate and reposition itself. */
	reposition() {
		if (!this.active || !this.anchorEl || !this.popup) return;
		const middleware = [offset({
			mainAxis: this.distance,
			crossAxis: this.skidding
		})];
		if (this.sync) middleware.push(size({ apply: ({ rects }) => {
			const syncWidth = this.sync === "width" || this.sync === "both";
			const syncHeight = this.sync === "height" || this.sync === "both";
			this.popup.style.width = syncWidth ? `${rects.reference.width}px` : "";
			this.popup.style.height = syncHeight ? `${rects.reference.height}px` : "";
		} }));
		else {
			this.popup.style.width = "";
			this.popup.style.height = "";
		}
		let defaultBoundary;
		if (this.SUPPORTS_POPOVER && !isVirtualElement(this.anchor) && this.boundary === "scroll") defaultBoundary = getOverflowAncestors(this.anchorEl).filter((el) => el instanceof Element);
		if (this.flip) middleware.push(flip({
			boundary: this.flipBoundary || defaultBoundary,
			fallbackPlacements: this.flipFallbackPlacements,
			fallbackStrategy: this.flipFallbackStrategy === "best-fit" ? "bestFit" : "initialPlacement",
			padding: this.flipPadding
		}));
		if (this.shift) middleware.push(shift({
			boundary: this.shiftBoundary || defaultBoundary,
			padding: this.shiftPadding
		}));
		if (this.autoSize) middleware.push(size({
			boundary: this.autoSizeBoundary || defaultBoundary,
			padding: this.autoSizePadding,
			apply: ({ availableWidth, availableHeight }) => {
				if (this.autoSize === "vertical" || this.autoSize === "both") this.style.setProperty("--auto-size-available-height", `${availableHeight}px`);
				else this.style.removeProperty("--auto-size-available-height");
				if (this.autoSize === "horizontal" || this.autoSize === "both") this.style.setProperty("--auto-size-available-width", `${availableWidth}px`);
				else this.style.removeProperty("--auto-size-available-width");
			}
		}));
		else {
			this.style.removeProperty("--auto-size-available-width");
			this.style.removeProperty("--auto-size-available-height");
		}
		if (this.arrow) middleware.push(arrow({
			element: this.arrowEl,
			padding: this.arrowPadding
		}));
		const getOffsetParent = this.SUPPORTS_POPOVER ? (element) => platform.getOffsetParent(element, e) : platform.getOffsetParent;
		computePosition(this.anchorEl, this.popup, {
			placement: this.placement,
			middleware,
			strategy: this.SUPPORTS_POPOVER ? "absolute" : "fixed",
			platform: {
				...platform,
				getOffsetParent
			}
		}).then(({ x, y, middlewareData, placement }) => {
			const isRtl = this.localize.dir() === "rtl";
			const staticSide = {
				top: "bottom",
				right: "left",
				bottom: "top",
				left: "right"
			}[placement.split("-")[0]];
			this.setAttribute("data-current-placement", placement);
			Object.assign(this.popup.style, {
				left: `${x}px`,
				top: `${y}px`
			});
			if (this.arrow) {
				const arrowX = middlewareData.arrow.x;
				const arrowY = middlewareData.arrow.y;
				let top = "";
				let right = "";
				let bottom = "";
				let left = "";
				if (this.arrowPlacement === "start") {
					const value = typeof arrowX === "number" ? `calc(${this.arrowPadding}px - var(--arrow-padding-offset))` : "";
					top = typeof arrowY === "number" ? `calc(${this.arrowPadding}px - var(--arrow-padding-offset))` : "";
					right = isRtl ? value : "";
					left = isRtl ? "" : value;
				} else if (this.arrowPlacement === "end") {
					const value = typeof arrowX === "number" ? `calc(${this.arrowPadding}px - var(--arrow-padding-offset))` : "";
					right = isRtl ? "" : value;
					left = isRtl ? value : "";
					bottom = typeof arrowY === "number" ? `calc(${this.arrowPadding}px - var(--arrow-padding-offset))` : "";
				} else if (this.arrowPlacement === "center") {
					left = typeof arrowX === "number" ? `calc(50% - var(--arrow-size-diagonal))` : "";
					top = typeof arrowY === "number" ? `calc(50% - var(--arrow-size-diagonal))` : "";
				} else {
					left = typeof arrowX === "number" ? `${arrowX}px` : "";
					top = typeof arrowY === "number" ? `${arrowY}px` : "";
				}
				Object.assign(this.arrowEl.style, {
					top,
					right,
					bottom,
					left,
					[staticSide]: "calc(var(--arrow-base-offset) - var(--arrow-size-diagonal))"
				});
			}
		});
		requestAnimationFrame(() => this.updateHoverBridge());
		this.dispatchEvent(new WaRepositionEvent());
	}
	render() {
		return b`
      <slot name="anchor" @slotchange=${this.handleAnchorChange}></slot>

      <span
        part="hover-bridge"
        class=${e$3({
			"popup-hover-bridge": true,
			"popup-hover-bridge-visible": this.hoverBridge && this.active
		})}
      ></span>

      <div
        popover="manual"
        part="popup"
        class=${e$3({
			popup: true,
			"popup-active": this.active,
			"popup-fixed": !this.SUPPORTS_POPOVER,
			"popup-has-arrow": this.arrow
		})}
      >
        <slot></slot>
        ${this.arrow ? b`<div part="arrow" class="arrow" role="presentation"></div>` : ""}
      </div>
    `;
	}
};
WaPopup.css = popup_styles_default;
__decorateClass([e$5(".popup")], WaPopup.prototype, "popup", 2);
__decorateClass([e$5(".arrow")], WaPopup.prototype, "arrowEl", 2);
__decorateClass([n$2({
	attribute: false,
	type: Boolean
})], WaPopup.prototype, "SUPPORTS_POPOVER", 2);
__decorateClass([n$2()], WaPopup.prototype, "anchor", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaPopup.prototype, "active", 2);
__decorateClass([n$2({ reflect: true })], WaPopup.prototype, "placement", 2);
__decorateClass([n$2()], WaPopup.prototype, "boundary", 2);
__decorateClass([n$2({ type: Number })], WaPopup.prototype, "distance", 2);
__decorateClass([n$2({ type: Number })], WaPopup.prototype, "skidding", 2);
__decorateClass([n$2({ type: Boolean })], WaPopup.prototype, "arrow", 2);
__decorateClass([n$2({ attribute: "arrow-placement" })], WaPopup.prototype, "arrowPlacement", 2);
__decorateClass([n$2({
	attribute: "arrow-padding",
	type: Number
})], WaPopup.prototype, "arrowPadding", 2);
__decorateClass([n$2({ type: Boolean })], WaPopup.prototype, "flip", 2);
__decorateClass([n$2({
	attribute: "flip-fallback-placements",
	converter: {
		fromAttribute: (value) => {
			return value.split(" ").map((p) => p.trim()).filter((p) => p !== "");
		},
		toAttribute: (value) => {
			return value.join(" ");
		}
	}
})], WaPopup.prototype, "flipFallbackPlacements", 2);
__decorateClass([n$2({ attribute: "flip-fallback-strategy" })], WaPopup.prototype, "flipFallbackStrategy", 2);
__decorateClass([n$2({ type: Object })], WaPopup.prototype, "flipBoundary", 2);
__decorateClass([n$2({
	attribute: "flip-padding",
	type: Number
})], WaPopup.prototype, "flipPadding", 2);
__decorateClass([n$2({ type: Boolean })], WaPopup.prototype, "shift", 2);
__decorateClass([n$2({ type: Object })], WaPopup.prototype, "shiftBoundary", 2);
__decorateClass([n$2({
	attribute: "shift-padding",
	type: Number
})], WaPopup.prototype, "shiftPadding", 2);
__decorateClass([n$2({ attribute: "auto-size" })], WaPopup.prototype, "autoSize", 2);
__decorateClass([n$2()], WaPopup.prototype, "sync", 2);
__decorateClass([n$2({ type: Object })], WaPopup.prototype, "autoSizeBoundary", 2);
__decorateClass([n$2({
	attribute: "auto-size-padding",
	type: Number
})], WaPopup.prototype, "autoSizePadding", 2);
__decorateClass([n$2({
	attribute: "hover-bridge",
	type: Boolean
})], WaPopup.prototype, "hoverBridge", 2);
WaPopup = __decorateClass([t$2("wa-popup")], WaPopup);
// node_modules/@awesome.me/webawesome/dist/components/select/select.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.DWWFIQKG.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var switch_styles_default = i$7`
  :host {
    --height: var(--wa-form-control-toggle-size);
    --width: calc(var(--height) * 1.75);
    --thumb-size: 0.75em;

    display: inline-flex;
    line-height: var(--wa-form-control-value-line-height);
  }

  label {
    position: relative;
    display: flex;
    align-items: center;
    font: inherit;
    color: var(--wa-form-control-value-color);
    vertical-align: middle;
    cursor: pointer;
  }

  .switch {
    flex: 0 0 auto;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--width);
    height: var(--height);
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--height);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    transition-property: translate, background, border-color, box-shadow;
    transition-duration: var(--wa-transition-normal);
    transition-timing-function: var(--wa-transition-easing);
  }

  :host([did-ssr]:not(:defined)) .switch {
    transition-property: unset;
    transition-duration: unset;
    transition-timing-function: unset;
  }

  .switch .thumb {
    aspect-ratio: 1 / 1;
    width: var(--thumb-size);
    height: var(--thumb-size);
    background-color: var(--wa-form-control-border-color);
    border-radius: 50%;
    translate: calc((var(--width) - var(--height)) / -2);
    transition: inherit;
  }
  .switch .thumb:dir(rtl) {
    translate: calc((var(--width) - var(--height)) / 2);
  }

  .input {
    position: absolute;
    opacity: 0;
    padding: 0;
    margin: 0;
    pointer-events: none;
  }

  /* Focus */
  label:not(.disabled) .input:focus-visible ~ [part~='control'] {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Checked */
  .checked .switch {
    background-color: var(--wa-form-control-activated-color);
    border-color: var(--wa-form-control-activated-color);
  }

  .checked .switch .thumb {
    background-color: var(--wa-color-surface-default);
    translate: calc((var(--width) - var(--height)) / 2);
  }
  .checked .switch .thumb:dir(rtl) {
    translate: calc((var(--width) - var(--height)) / -2);
  }

  /* Disabled */
  label:has(> :disabled) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  [part~='label'] {
    display: inline-block;
    line-height: var(--height);
    margin-inline-start: 0.5em;
    user-select: none;
    -webkit-user-select: none;
  }

  :host([required]) [part~='label']::after {
    content: var(--wa-form-control-required-content);
    color: var(--wa-form-control-required-content-color);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }

  @media (forced-colors: active) {
    :checked:enabled + .switch:hover .thumb,
    :checked + .switch .thumb {
      background-color: ButtonText;
    }
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.FZZRDCIJ.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaSwitch = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super(...arguments);
		this.hasSlotController = new HasSlotController(this, "hint");
		this.localize = new LocalizeController(this);
		this.title = "";
		this.name = null;
		this._value = this.getAttribute("value") ?? null;
		this.size = "m";
		this.disabled = false;
		this._checked = null;
		this.defaultChecked = this.hasAttribute("checked");
		this.required = false;
		this.hint = "";
		this.withHint = false;
	}
	static get validators() {
		return [...super.validators, MirrorValidator()];
	}
	/** The value of the switch, submitted as a name/value pair with form data. */
	get value() {
		return this._value ?? "on";
	}
	set value(val) {
		this._value = val;
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	get checked() {
		if (this.valueHasChanged) return Boolean(this._checked);
		return this._checked ?? this.defaultChecked;
	}
	set checked(val) {
		this._checked = Boolean(val);
		this.valueHasChanged = true;
	}
	handleClick() {
		this.hasInteracted = true;
		this.checked = !this.checked;
		this.updateComplete.then(() => {
			this.dispatchEvent(new Event("change", {
				bubbles: true,
				composed: true
			}));
		});
	}
	handleKeyDown(event) {
		const isRtl = this.localize.dir() === "rtl";
		if (event.key === "ArrowLeft") {
			event.preventDefault();
			if (this.checked === isRtl) return;
			this.checked = isRtl;
			this.updateComplete.then(() => {
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
			});
		}
		if (event.key === "ArrowRight") {
			event.preventDefault();
			if (this.checked === !isRtl) return;
			this.checked = !isRtl;
			this.updateComplete.then(() => {
				this.dispatchEvent(new Event("change", {
					bubbles: true,
					composed: true
				}));
				this.dispatchEvent(new InputEvent("input", {
					bubbles: true,
					composed: true
				}));
			});
		}
	}
	willUpdate(changedProperties) {
		super.willUpdate(changedProperties);
		if (changedProperties.has("value") || changedProperties.has("checked") || changedProperties.has("defaultChecked") || changedProperties.has("disabled")) this.handleValueOrCheckedChange();
	}
	handleValueOrCheckedChange() {
		if (this.didSSR && !this.hasUpdated) {
			this.updateComplete.then(() => {
				this.handleValueOrCheckedChange();
			});
			return;
		}
		this.setValue(this.checked ? this.value : null, this._value);
		this.updateValidity();
	}
	handleStateChange() {
		if (this.hasUpdated) this.input.checked = this.checked;
		this.customStates.set("checked", this.checked);
		this.updateValidity();
	}
	handleDisabledChange() {
		this.updateValidity();
	}
	/** Simulates a click on the switch. */
	click() {
		this.input.click();
	}
	/** Sets focus on the switch. */
	focus(options) {
		this.input.focus(options);
	}
	/** Removes focus from the switch. */
	blur() {
		this.input.blur();
	}
	setValue(value, stateValue) {
		if (!this.checked) {
			this.internals.setFormValue(null, null);
			return;
		}
		this.internals.setFormValue(value ?? "on", stateValue);
	}
	formResetCallback() {
		this._checked = null;
		super.formResetCallback();
		this.handleValueOrCheckedChange();
	}
	render() {
		const hasHintSlot = this.hasSlotController.test("hint", "withHint");
		const hasHint = this.hint ? true : !!hasHintSlot;
		const checkedAttribute = this.didSSR && !this.hasUpdated ? this.checked : this.defaultChecked;
		const checkedProperty = this.didSSR && !this.hasUpdated ? null : l(this.checked);
		return b`
      <label
        part="base switch"
        class=${e$3({
			checked: this.checked,
			disabled: this.disabled
		})}
      >
        <input
          class="input"
          type="checkbox"
          title=${this.title}
          name=${o$2(this.name)}
          value=${o$2(this.value)}
          .checked=${o$2(checkedProperty)}
          ?checked=${checkedAttribute}
          ?disabled=${this.disabled}
          ?required=${this.required}
          role="switch"
          aria-checked=${this.checked ? "true" : "false"}
          aria-describedby="hint"
          @click=${this.handleClick}
          @keydown=${this.handleKeyDown}
        />

        <span part="control" class="switch">
          <span part="thumb" class="thumb"></span>
        </span>

        <slot part="label" class="label"></slot>
      </label>

      <slot
        id="hint"
        name="hint"
        part="hint"
        class=${e$3({ "has-slotted": hasHint })}
        aria-hidden=${hasHint ? "false" : "true"}
        >${this.hint}</slot
      >
    `;
	}
};
WaSwitch.shadowRootOptions = {
	...WebAwesomeFormAssociatedElement.shadowRootOptions,
	delegatesFocus: true
};
WaSwitch.css = [
	form_control_styles_default,
	size_styles_default,
	switch_styles_default
];
__decorateClass([e$5("input[type=\"checkbox\"]")], WaSwitch.prototype, "input", 2);
__decorateClass([n$2()], WaSwitch.prototype, "title", 2);
__decorateClass([n$2({ reflect: true })], WaSwitch.prototype, "name", 2);
__decorateClass([n$2({ reflect: true })], WaSwitch.prototype, "value", 1);
__decorateClass([n$2({ reflect: true })], WaSwitch.prototype, "size", 2);
__decorateClass([watch("size")], WaSwitch.prototype, "handleSizeChange", 1);
__decorateClass([n$2({ type: Boolean })], WaSwitch.prototype, "disabled", 2);
__decorateClass([n$2({
	type: Boolean,
	attribute: false
})], WaSwitch.prototype, "checked", 1);
__decorateClass([n$2({
	type: Boolean,
	attribute: "checked",
	reflect: true
})], WaSwitch.prototype, "defaultChecked", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaSwitch.prototype, "required", 2);
__decorateClass([n$2({ attribute: "hint" })], WaSwitch.prototype, "hint", 2);
__decorateClass([n$2({
	attribute: "with-hint",
	type: Boolean
})], WaSwitch.prototype, "withHint", 2);
__decorateClass([watch(["checked", "defaultChecked"])], WaSwitch.prototype, "handleStateChange", 1);
__decorateClass([watch("disabled", { waitUntilFirstUpdate: true })], WaSwitch.prototype, "handleDisabledChange", 1);
WaSwitch = __decorateClass([t$2("wa-switch")], WaSwitch);
WaSwitch.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/components/switch/switch.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.IOB2JHMR.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var textarea_styles_default = i$7`
  :host {
    border-width: 0;
  }

  .textarea {
    display: grid;
    align-items: center;
    margin: 0;
    border: none;
    outline: none;
    cursor: inherit;
    font: inherit;
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    -webkit-appearance: none;
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    &:focus-within {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled textareas */
    &:has(:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .textarea {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .textarea {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .textarea {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  textarea {
    display: block;
    width: 100%;
    border: none;
    background: transparent;
    font: inherit;
    color: inherit;
    cursor: inherit;
    scroll-padding-block: var(--wa-form-control-padding-block);
    padding: calc(var(--wa-form-control-padding-block) - ((1lh - 1em) / 2)) var(--wa-form-control-padding-inline); /* accounts for the larger line height of textarea content */
    min-height: calc(var(--wa-form-control-height) - var(--border-width) * 2);
    box-shadow: none;
    margin: 0;

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }

    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &:focus {
      outline: none;
    }
  }

  /* Shared textarea and size-adjuster positioning */
  .control,
  .size-adjuster {
    grid-area: 1 / 1 / 2 / 2;
  }

  .size-adjuster {
    visibility: hidden;
    pointer-events: none;
    opacity: 0;
    padding: 0;
  }

  textarea::-webkit-search-decoration,
  textarea::-webkit-search-cancel-button,
  textarea::-webkit-search-results-button,
  textarea::-webkit-search-results-decoration {
    -webkit-appearance: none;
  }

  /*
   * Resize types
   */

  :host([resize='none']) textarea {
    resize: none;
  }

  textarea,
  :host([resize='vertical']) textarea {
    resize: vertical;
  }

  :host([resize='horizontal']) textarea {
    resize: horizontal;
  }

  :host([resize='both']) textarea {
    resize: both;
  }

  :host([resize='auto']) textarea {
    height: auto;
    resize: none;
    overflow-y: hidden;
  }

  /*
   * Footer (hint + character count)
   */

  /*
   * This element carries the hint part, so the shared form control styles apply to it. Those styles set display:block
   * and hide the element when it has no hint, both of which have to be undone when a character count is present.
   */
  .footer.has-slotted,
  .footer.has-count {
    display: flex;
    align-items: baseline;
    gap: 1em;
  }

  /* Slots default to display:contents, which would leave the hint unable to shrink below its content */
  .footer.has-count .hint {
    display: block;
    flex: 1 1 auto;
    min-width: 0;
  }

  .count {
    flex: 0 0 auto;
    color: var(--wa-form-control-hint-color);
    font-weight: var(--wa-form-control-hint-font-weight);
    line-height: var(--wa-form-control-hint-line-height);
    margin-block-start: 0.5em;
    font-size: var(--wa-font-size-smaller);
    margin-inline-start: auto;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.HEEBTYY6.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var visually_hidden_styles_default = i$7`
  .wa-visually-hidden:not(:focus-within),
  .wa-visually-hidden-force,
  .wa-visually-hidden-hint::part(hint),
  .wa-visually-hidden-label::part(label),
  .wa-visually-hidden-label::part(form-control-label) {
    top: 0px !important;
    left: 0px !important;
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    clip: rect(0 0 0 0) !important;
    clip-path: inset(50%) !important;
    border: none !important;
    overflow: hidden !important;
    white-space: nowrap !important;
    padding: 0 !important;
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.32KCEW6F.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var WaTextarea = class extends WebAwesomeFormAssociatedElement {
	constructor() {
		super(...arguments);
		this.assumeInteractionOn = ["blur", "input"];
		this.hasSlotController = new HasSlotController(this, "hint", "label");
		this.localize = new LocalizeController(this);
		this.announcedCountText = "";
		this.title = "";
		this.name = null;
		this._value = null;
		this.defaultValue = this.getAttribute("value") ?? "";
		this.size = "m";
		this.appearance = "outlined";
		this.label = "";
		this.hint = "";
		this.placeholder = "";
		this.rows = 4;
		this.resize = "vertical";
		this.disabled = false;
		this.readonly = false;
		this.required = false;
		this.spellcheck = true;
		this.withLabel = false;
		this.withHint = false;
		this.withCount = false;
		this.lastObservedWidth = 0;
	}
	static get validators() {
		return [...super.validators, MirrorValidator()];
	}
	/** The current value of the input, submitted as a name/value pair with form data. */
	get value() {
		if (this.valueHasChanged) return this._value;
		return this._value ?? this.defaultValue;
	}
	set value(val) {
		if (this._value === val) return;
		this.valueHasChanged = true;
		this._value = val;
	}
	handleSizeChange() {
		warnDeprecatedSize(this.localName, this.size);
	}
	connectedCallback() {
		super.connectedCallback();
		this.updateComplete.then(() => {
			this.setTextareaDimensions();
			this.updateResizeObserver();
			if (this.didSSR && this.input && this.value !== this.input.value) {
				const value = this.input.value;
				this.value = value;
			}
		});
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		clearTimeout(this.countAnnounceTimeout);
		this.resizeObserver?.disconnect();
		this.resizeObserver = void 0;
	}
	/**
	* @internal
	*/
	updateFormValue(value) {
		if (value == null) {
			this.setValue("", null);
			return;
		}
		super.updateFormValue(value);
	}
	/** Creates or destroys the resize observer based on the current resize mode. */
	updateResizeObserver() {
		const needsObserver = this.resize !== "none";
		if (this.resizeObserver) {
			this.resizeObserver.disconnect();
			this.resizeObserver = void 0;
		}
		if (needsObserver && this.input) {
			if (this.resize === "auto") {
				this.resizeObserver = new ResizeObserver((entries) => {
					const width = entries[0]?.contentRect.width ?? 0;
					if (width !== this.lastObservedWidth) {
						this.lastObservedWidth = width;
						requestAnimationFrame(() => this.setTextareaDimensions());
					}
				});
				this.resizeObserver.observe(this);
			} else {
				this.resizeObserver = new ResizeObserver(() => this.setTextareaDimensions());
				this.resizeObserver.observe(this.input);
			}
		}
	}
	handleBlur() {
		this.checkValidity();
	}
	handleChange(event) {
		this.valueHasChanged = true;
		this.value = this.input.value;
		this.setTextareaDimensions();
		this.checkValidity();
		this.relayNativeEvent(event, {
			bubbles: true,
			composed: true
		});
	}
	handleInput(event) {
		this.valueHasChanged = true;
		this.value = this.input.value;
		this.relayNativeEvent(event, {
			bubbles: true,
			composed: true
		});
		this.scheduleCountAnnouncement();
	}
	scheduleCountAnnouncement() {
		clearTimeout(this.countAnnounceTimeout);
		this.countAnnounceTimeout = setTimeout(() => {
			const currentLength = (this.value ?? "").length;
			this.announcedCountText = this.maxlength != null ? this.localize.term("numCharactersRemaining", this.maxlength - currentLength) : this.localize.term("numCharacters", currentLength);
		}, 1e3);
	}
	setTextareaDimensions() {
		if (this.resize === "none") {
			this.wrapper.style.width = ``;
			this.wrapper.style.height = ``;
			return;
		}
		if (this.resize === "auto") {
			this.sizeAdjuster.style.height = `${this.input.clientHeight}px`;
			this.input.style.height = "auto";
			const newHeight = this.input.scrollHeight;
			this.input.style.height = `${newHeight}px`;
			this.sizeAdjuster.style.height = `${newHeight}px`;
			this.wrapper.style.width = ``;
			this.wrapper.style.height = ``;
			return;
		}
		if (this.input.style.width) {
			const width = Number(this.input.style.width.split(/px/)[0]) + 2;
			this.wrapper.style.width = `${width}px`;
		}
		if (this.input.style.height) {
			const height = Number(this.input.style.height.split(/px/)[0]) + 2;
			this.wrapper.style.height = `${height}px`;
		}
	}
	handleRowsChange() {
		this.setTextareaDimensions();
	}
	async handleValueChange() {
		await this.updateComplete;
		this.checkValidity();
		this.setTextareaDimensions();
	}
	updated(changedProperties) {
		if (changedProperties.has("resize")) {
			this.setTextareaDimensions();
			this.updateResizeObserver();
		}
		super.updated(changedProperties);
		if (changedProperties.has("value")) this.customStates.set("blank", !this.value);
	}
	/** Sets focus on the textarea. */
	focus(options) {
		this.input.focus(options);
	}
	/** Removes focus from the textarea. */
	blur() {
		this.input.blur();
	}
	/** Selects all the text in the textarea. */
	select() {
		this.input.select();
	}
	/** Gets or sets the textarea's scroll position. */
	scrollPosition(position) {
		if (position) {
			if (typeof position.top === "number") this.input.scrollTop = position.top;
			if (typeof position.left === "number") this.input.scrollLeft = position.left;
			return;
		}
		return {
			top: this.input.scrollTop,
			left: this.input.scrollLeft
		};
	}
	/** Sets the start and end positions of the text selection (0-based). */
	setSelectionRange(selectionStart, selectionEnd, selectionDirection = "none") {
		this.input.setSelectionRange(selectionStart, selectionEnd, selectionDirection);
	}
	/** Replaces a range of text with a new string. */
	setRangeText(replacement, start, end, selectMode = "preserve") {
		const selectionStart = start ?? this.input.selectionStart;
		const selectionEnd = end ?? this.input.selectionEnd;
		this.input.setRangeText(replacement, selectionStart, selectionEnd, selectMode);
		if (this.value !== this.input.value) {
			this.value = this.input.value;
			this.setTextareaDimensions();
		}
	}
	formResetCallback() {
		this._value = null;
		if (this.input) this.input.value = this.value || "";
		super.formResetCallback();
	}
	render() {
		const hasLabelSlot = this.hasSlotController.test("label", "withLabel");
		const hasHintSlot = this.hasSlotController.test("hint", "withHint");
		const hasLabel = this.label ? true : !!hasLabelSlot;
		const hasHint = this.hint ? true : !!hasHintSlot;
		const currentLength = (this.value ?? "").length;
		const countText = this.maxlength != null ? this.localize.term("numCharactersRemaining", this.maxlength - currentLength) : this.localize.term("numCharacters", currentLength);
		return b`
      <label
        part="form-control-label label"
        class=${e$3({
			label: true,
			"has-label": hasLabel
		})}
        for="input"
        aria-hidden=${hasLabel ? "false" : "true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base textarea-wrapper" class="textarea">
        <textarea
          part="textarea"
          id="input"
          class="control"
          title=${this.title}
          name=${o$2(this.name)}
          .value=${l(this.value)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${o$2(this.placeholder)}
          rows=${o$2(this.rows)}
          minlength=${o$2(this.minlength)}
          maxlength=${o$2(this.maxlength)}
          autocapitalize=${o$2(this.autocapitalize)}
          autocorrect=${o$2(this.autocorrect)}
          ?autofocus=${this.autofocus}
          spellcheck=${o$2(this.spellcheck)}
          enterkeyhint=${o$2(this.enterkeyhint)}
          inputmode=${o$2(this.inputmode)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @blur=${this.handleBlur}
        ></textarea>

        <!-- This "adjuster" exists to prevent layout shifting. https://github.com/shoelace-style/shoelace/issues/2180 -->
        <div part="textarea-adjuster" class="size-adjuster" ?hidden=${this.resize !== "auto"}></div>
      </div>

      <div
        part="hint"
        class=${e$3({
			footer: true,
			"has-count": this.withCount,
			"has-slotted": hasHint
		})}
      >
        <slot id="hint" name="hint" class="hint" aria-hidden=${hasHint ? "false" : "true"}>${this.hint}</slot>

        ${this.withCount ? b`
              <div part="count" class="count" aria-hidden="true">${countText}</div>
              <div class="wa-visually-hidden-force" aria-live="polite">${this.announcedCountText}</div>
            ` : ""}
      </div>
    `;
	}
};
WaTextarea.css = [
	textarea_styles_default,
	form_control_styles_default,
	size_styles_default,
	visually_hidden_styles_default
];
__decorateClass([r$2()], WaTextarea.prototype, "announcedCountText", 2);
__decorateClass([e$5(".control")], WaTextarea.prototype, "input", 2);
__decorateClass([e$5("[part~=\"textarea-wrapper\"]")], WaTextarea.prototype, "wrapper", 2);
__decorateClass([e$5("[part~=\"textarea-wrapper\"]")], WaTextarea.prototype, "base", 2);
__decorateClass([e$5(".size-adjuster")], WaTextarea.prototype, "sizeAdjuster", 2);
__decorateClass([n$2()], WaTextarea.prototype, "title", 2);
__decorateClass([n$2({ reflect: true })], WaTextarea.prototype, "name", 2);
__decorateClass([r$2()], WaTextarea.prototype, "value", 1);
__decorateClass([n$2({
	attribute: "value",
	reflect: true
})], WaTextarea.prototype, "defaultValue", 2);
__decorateClass([n$2({ reflect: true })], WaTextarea.prototype, "size", 2);
__decorateClass([watch("size")], WaTextarea.prototype, "handleSizeChange", 1);
__decorateClass([n$2({ reflect: true })], WaTextarea.prototype, "appearance", 2);
__decorateClass([n$2()], WaTextarea.prototype, "label", 2);
__decorateClass([n$2({ attribute: "hint" })], WaTextarea.prototype, "hint", 2);
__decorateClass([n$2()], WaTextarea.prototype, "placeholder", 2);
__decorateClass([n$2({ type: Number })], WaTextarea.prototype, "rows", 2);
__decorateClass([n$2({ reflect: true })], WaTextarea.prototype, "resize", 2);
__decorateClass([n$2({ type: Boolean })], WaTextarea.prototype, "disabled", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaTextarea.prototype, "readonly", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaTextarea.prototype, "required", 2);
__decorateClass([n$2({ type: Number })], WaTextarea.prototype, "minlength", 2);
__decorateClass([n$2({ type: Number })], WaTextarea.prototype, "maxlength", 2);
__decorateClass([n$2()], WaTextarea.prototype, "autocapitalize", 2);
__decorateClass([n$2({
	type: Boolean,
	converter: {
		fromAttribute: (value) => !value || value === "off" ? false : true,
		toAttribute: (value) => value ? "on" : "off"
	}
})], WaTextarea.prototype, "autocorrect", 2);
__decorateClass([n$2()], WaTextarea.prototype, "autocomplete", 2);
__decorateClass([n$2({ type: Boolean })], WaTextarea.prototype, "autofocus", 2);
__decorateClass([n$2()], WaTextarea.prototype, "enterkeyhint", 2);
__decorateClass([n$2({
	type: Boolean,
	converter: {
		fromAttribute: (value) => !value || value === "false" ? false : true,
		toAttribute: (value) => value ? "true" : "false"
	}
})], WaTextarea.prototype, "spellcheck", 2);
__decorateClass([n$2()], WaTextarea.prototype, "inputmode", 2);
__decorateClass([n$2({
	attribute: "with-label",
	type: Boolean
})], WaTextarea.prototype, "withLabel", 2);
__decorateClass([n$2({
	attribute: "with-hint",
	type: Boolean
})], WaTextarea.prototype, "withHint", 2);
__decorateClass([n$2({
	attribute: "with-count",
	type: Boolean,
	reflect: true
})], WaTextarea.prototype, "withCount", 2);
__decorateClass([watch("rows", { waitUntilFirstUpdate: true })], WaTextarea.prototype, "handleRowsChange", 1);
__decorateClass([watch("value", { waitUntilFirstUpdate: true })], WaTextarea.prototype, "handleValueChange", 1);
WaTextarea = __decorateClass([t$2("wa-textarea")], WaTextarea);
WaTextarea.disableWarning?.("change-in-update");
// node_modules/@awesome.me/webawesome/dist/components/textarea/textarea.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.DJLBC7Q4.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
var tooltip_styles_default = i$7`
  :host {
    --max-width: 30ch;

    /** These styles are added so we don't interfere in the DOM. */
    display: inline-block;
    position: absolute;

    /** Defaults for inherited CSS properties */
    color: var(--wa-tooltip-content-color);
    font-size: var(--wa-tooltip-font-size);
    line-height: var(--wa-tooltip-line-height);
    text-align: start;
    white-space: normal;
  }

  .tooltip {
    --arrow-size: var(--wa-tooltip-arrow-size);
    --arrow-color: var(--wa-tooltip-background-color);
  }

  .tooltip::part(popup) {
    z-index: 1000;
  }

  .tooltip[placement^='top']::part(popup) {
    transform-origin: bottom;
  }

  .tooltip[placement^='bottom']::part(popup) {
    transform-origin: top;
  }

  .tooltip[placement^='left']::part(popup) {
    transform-origin: right;
  }

  .tooltip[placement^='right']::part(popup) {
    transform-origin: left;
  }

  .body {
    display: block;
    width: max-content;
    max-width: var(--max-width);
    border-radius: var(--wa-tooltip-border-radius);
    background-color: var(--wa-tooltip-background-color);
    border: var(--wa-tooltip-border-width) var(--wa-tooltip-border-style) var(--wa-tooltip-border-color);
    padding: 0.25em 0.5em;
    user-select: none;
    -webkit-user-select: none;
  }

  .tooltip {
    --popup-border-width: var(--wa-tooltip-border-width);

    /* Inset box-shadow, not a border: Safari seams a clip-path edge that runs along a border. */
    &::part(arrow) {
      box-shadow: inset calc(-1 * var(--wa-tooltip-border-width)) calc(-1 * var(--wa-tooltip-border-width)) 0 0
        var(--wa-tooltip-border-color);
    }
  }
`;
// node_modules/@awesome.me/webawesome/dist/chunks/chunk.U6U6F4KE.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
function containsComposedNode(ancestor, node) {
	while (node) {
		if (node === ancestor) return true;
		if (node instanceof Element && node.assignedSlot) node = node.assignedSlot;
		else if (node.parentNode) node = node.parentNode;
		else if (node instanceof ShadowRoot) node = node.host;
		else node = null;
	}
	return false;
}
var WaTooltip = class extends WebAwesomeElement {
	constructor() {
		super(...arguments);
		this.dismissedByPress = false;
		this.placement = "top";
		this.disabled = false;
		this.distance = 8;
		this.open = false;
		this.skidding = 0;
		this.showDelay = 150;
		this.hideDelay = 0;
		this.trigger = "hover focus";
		this.withoutArrow = false;
		this.for = null;
		this.anchor = null;
		this.eventController = new AbortController();
		this.handleBlur = () => {
			this.dismissedByPress = false;
			if (this.hasTrigger("focus")) this.hide();
		};
		this.handleClick = (event) => {
			if (this.hasTrigger("click")) {
				if (this.open) this.hide();
				else this.show();
				return;
			}
			if (this.hasTrigger("manual")) return;
			if (event.detail === 0) this.lightDismiss();
		};
		this.handleFocus = () => {
			if (this.dismissedByPress) return;
			if (this.hasTrigger("focus")) this.show();
		};
		this.handlePointerDown = (event) => {
			if (event.pointerType === "touch" || this.hasTrigger("click") || this.hasTrigger("manual")) return;
			this.lightDismiss();
		};
		this.handleDocumentKeyDown = (event) => {
			if (this.hasTrigger("manual")) return;
			if (event.key === "Escape" && this.open && isTopDismissible(this)) {
				event.preventDefault();
				event.stopPropagation();
				this.hide();
			}
		};
		this.handleDocumentClick = (event) => {
			if (this.hasTrigger("manual")) return;
			if (this.anchor && event.composedPath().includes(this.anchor)) return;
			this.hide();
		};
		this.handleMouseOver = () => {
			if (this.dismissedByPress) return;
			if (this.hasTrigger("hover")) {
				clearTimeout(this.hoverTimeout);
				this.hoverTimeout = window.setTimeout(() => this.show(), this.showDelay);
			}
		};
		this.handleMouseOut = (event) => {
			const relatedTarget = event.relatedTarget;
			const movedIntoAnchor = Boolean(relatedTarget && this.anchor && containsComposedNode(this.anchor, relatedTarget));
			const movedIntoTooltip = Boolean(relatedTarget && containsComposedNode(this, relatedTarget));
			if (movedIntoAnchor || movedIntoTooltip) return;
			this.dismissedByPress = false;
			if (this.hasTrigger("hover")) {
				clearTimeout(this.hoverTimeout);
				this.hoverTimeout = window.setTimeout(() => {
					this.hide();
				}, this.hideDelay);
			}
		};
	}
	connectedCallback() {
		super.connectedCallback();
		if (typeof document !== "undefined") {
			if (this.eventController.signal.aborted) this.eventController = new AbortController();
			this.addEventListener("mouseout", this.handleMouseOut);
			this.dismissedByPress = false;
			if (this.open) {
				this.open = false;
				this.updateComplete.then(() => {
					if (this.disabled) return;
					this.open = true;
				});
			}
			if (!this.id) this.id = uniqueId("wa-tooltip-");
			if (this.for && this.anchor) {
				this.anchor = null;
				this.handleForChange();
			} else if (this.for) this.handleForChange();
		}
	}
	disconnectedCallback() {
		super.disconnectedCallback();
		document.removeEventListener("keydown", this.handleDocumentKeyDown);
		document.removeEventListener("click", this.handleDocumentClick);
		unregisterDismissible(this);
		this.eventController.abort(null);
		if (this.anchor) this.removeFromAriaLabelledBy(this.anchor, this.id);
	}
	firstUpdated(changedProperties) {
		this.body.hidden = !this.open;
		if (this.open) {
			this.popup.active = true;
			this.popup.reposition();
		}
		super.firstUpdated(changedProperties);
	}
	/** Hides the tooltip, or cancels a pending show, and keeps it hidden until re-armed. */
	lightDismiss() {
		clearTimeout(this.hoverTimeout);
		this.dismissedByPress = true;
		this.hide();
	}
	hasTrigger(triggerType) {
		return this.trigger.split(" ").includes(triggerType);
	}
	/** Adds the tooltip ID to the aria-labelledby attribute */
	addToAriaLabelledBy(element, id) {
		const labels = (element.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean);
		if (!labels.includes(id)) {
			labels.push(id);
			element.setAttribute("aria-labelledby", labels.join(" "));
		}
	}
	/** Removes the tooltip ID from the aria-labelledby attribute */
	removeFromAriaLabelledBy(element, id) {
		const filteredLabels = (element.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean).filter((label) => label !== id);
		if (filteredLabels.length > 0) element.setAttribute("aria-labelledby", filteredLabels.join(" "));
		else element.removeAttribute("aria-labelledby");
	}
	async handleOpenChange() {
		if (this.open) {
			if (this.disabled) {
				this.open = false;
				return;
			}
			const waShowEvent = new WaShowEvent();
			this.dispatchEvent(waShowEvent);
			if (waShowEvent.defaultPrevented) {
				this.open = false;
				return;
			}
			if (!this.hasTrigger("manual")) {
				document.addEventListener("keydown", this.handleDocumentKeyDown, { signal: this.eventController.signal });
				document.addEventListener("click", this.handleDocumentClick, { signal: this.eventController.signal });
				registerDismissible(this);
			}
			this.body.hidden = false;
			this.popup.active = true;
			await animateWithClass(this.popup.popup, "show-with-scale");
			this.popup.reposition();
			this.dispatchEvent(new WaAfterShowEvent());
		} else {
			const waHideEvent = new WaHideEvent();
			this.dispatchEvent(waHideEvent);
			if (waHideEvent.defaultPrevented) {
				this.open = true;
				return;
			}
			document.removeEventListener("keydown", this.handleDocumentKeyDown);
			document.removeEventListener("click", this.handleDocumentClick);
			unregisterDismissible(this);
			await animateWithClass(this.popup.popup, "hide-with-scale");
			this.popup.active = false;
			this.body.hidden = true;
			this.dispatchEvent(new WaAfterHideEvent());
		}
	}
	handleForChange() {
		const rootNode = this.getRootNode?.();
		if (!rootNode) return;
		const newAnchor = this.for ? rootNode.getElementById?.(this.for) : null;
		const oldAnchor = this.anchor;
		if (newAnchor === oldAnchor) return;
		this.dismissedByPress = false;
		const { signal } = this.eventController;
		if (newAnchor) {
			this.addToAriaLabelledBy(newAnchor, this.id);
			newAnchor.addEventListener("blur", this.handleBlur, {
				capture: true,
				signal
			});
			newAnchor.addEventListener("focus", this.handleFocus, {
				capture: true,
				signal
			});
			newAnchor.addEventListener("click", this.handleClick, { signal });
			newAnchor.addEventListener("pointerdown", this.handlePointerDown, { signal });
			newAnchor.addEventListener("mouseover", this.handleMouseOver, { signal });
			newAnchor.addEventListener("mouseout", this.handleMouseOut, { signal });
		}
		if (oldAnchor) {
			this.removeFromAriaLabelledBy(oldAnchor, this.id);
			oldAnchor.removeEventListener("blur", this.handleBlur, { capture: true });
			oldAnchor.removeEventListener("focus", this.handleFocus, { capture: true });
			oldAnchor.removeEventListener("click", this.handleClick);
			oldAnchor.removeEventListener("pointerdown", this.handlePointerDown);
			oldAnchor.removeEventListener("mouseover", this.handleMouseOver);
			oldAnchor.removeEventListener("mouseout", this.handleMouseOut);
		}
		this.anchor = newAnchor;
	}
	async handleOptionsChange() {
		if (this.hasUpdated) {
			await this.updateComplete;
			this.popup.reposition();
		}
	}
	handleDisabledChange() {
		if (this.disabled && this.open) this.hide();
	}
	/** Shows the tooltip. */
	async show() {
		if (this.open || this.disabled) return;
		this.open = true;
		return waitForEvent(this, "wa-after-show");
	}
	/** Hides the tooltip */
	async hide() {
		if (!this.open) return;
		this.open = false;
		return waitForEvent(this, "wa-after-hide");
	}
	render() {
		return b`
      <wa-popup
        part="base tooltip"
        exportparts="
          popup:base__popup,
          arrow:base__arrow,
          popup:tooltip__popup,
          arrow:tooltip__arrow
        "
        class=${e$3({
			tooltip: true,
			"tooltip-open": this.open
		})}
        placement=${this.placement}
        distance=${this.distance}
        skidding=${this.skidding}
        flip
        shift
        ?arrow=${!this.withoutArrow}
        hover-bridge
        .anchor=${this.anchor}
      >
        <div part="body" class="body">
          <slot></slot>
        </div>
      </wa-popup>
    `;
	}
};
WaTooltip.css = tooltip_styles_default;
WaTooltip.dependencies = { "wa-popup": WaPopup };
__decorateClass([e$5("slot:not([name])")], WaTooltip.prototype, "defaultSlot", 2);
__decorateClass([e$5(".body")], WaTooltip.prototype, "body", 2);
__decorateClass([e$5("wa-popup")], WaTooltip.prototype, "popup", 2);
__decorateClass([n$2()], WaTooltip.prototype, "placement", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaTooltip.prototype, "disabled", 2);
__decorateClass([n$2({ type: Number })], WaTooltip.prototype, "distance", 2);
__decorateClass([n$2({
	type: Boolean,
	reflect: true
})], WaTooltip.prototype, "open", 2);
__decorateClass([n$2({ type: Number })], WaTooltip.prototype, "skidding", 2);
__decorateClass([n$2({
	attribute: "show-delay",
	type: Number
})], WaTooltip.prototype, "showDelay", 2);
__decorateClass([n$2({
	attribute: "hide-delay",
	type: Number
})], WaTooltip.prototype, "hideDelay", 2);
__decorateClass([n$2()], WaTooltip.prototype, "trigger", 2);
__decorateClass([n$2({
	attribute: "without-arrow",
	type: Boolean,
	reflect: true
})], WaTooltip.prototype, "withoutArrow", 2);
__decorateClass([n$2()], WaTooltip.prototype, "for", 2);
__decorateClass([r$2()], WaTooltip.prototype, "anchor", 2);
__decorateClass([watch("open", { waitUntilFirstUpdate: true })], WaTooltip.prototype, "handleOpenChange", 1);
__decorateClass([watch("for")], WaTooltip.prototype, "handleForChange", 1);
__decorateClass([watch([
	"distance",
	"placement",
	"skidding"
])], WaTooltip.prototype, "handleOptionsChange", 1);
__decorateClass([watch("disabled")], WaTooltip.prototype, "handleDisabledChange", 1);
WaTooltip = __decorateClass([t$2("wa-tooltip")], WaTooltip);
// node_modules/@awesome.me/webawesome/dist/components/tooltip/tooltip.js
/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
// src/sentinel-chart.js
var SentinelChart = class extends i$4 {
	static properties = {
		values: { attribute: false },
		min: { type: Number },
		max: { type: Number },
		threshold: { type: String },
		height: { type: Number },
		compact: {
			type: Boolean,
			reflect: true
		}
	};
	static styles = i$7`
    :host {
      display: block;
      min-inline-size: 0;
    }

    :host([compact]) {
      display: inline-block;
      inline-size: 4.5rem;
      vertical-align: middle;
    }

    svg {
      display: block;
      inline-size: 100%;
    }

    path {
      fill: none;
      stroke-width: 1.5;
      stroke-linecap: round;
      stroke-linejoin: round;
      vector-effect: non-scaling-stroke;
    }
  `;
	constructor() {
		super();
		this.values = [];
		this.height = 4;
		this.compact = false;
	}
	render() {
		const values = this.values.filter(Number.isFinite);
		if (values.length < 2) return "";
		const minimum = this.min ?? Math.min(...values);
		const maximum = this.max ?? Math.max(...values);
		const y = (value) => maximum === minimum ? 25 : 2 + 46 * (maximum - value) / (maximum - minimum);
		const points = values.map((value, index) => `${index === 0 ? "M" : "L"}${2 + 196 * index / (values.length - 1)},${y(value)}`).join(" ");
		const threshold = this.threshold ? Number(this.threshold) : NaN;
		return b`
      <svg
        aria-hidden="true"
        viewBox="0 0 200 50"
        preserveAspectRatio="none"
        style="block-size: ${this.compact ? 1.4 : this.height * 1.25}rem"
      >
        ${Number.isFinite(threshold) ? this.renderThreshold(points, y(threshold)) : w`
          <path d=${points} stroke="var(--wa-color-text-quiet)"></path>
        `}
      </svg>
    `;
	}
	renderThreshold(points, position) {
		const y = Math.max(0, Math.min(position, 50));
		return w`
      <defs>
        <clipPath id="above"><rect width="200" height=${y}></rect></clipPath>
        <clipPath id="below"><rect y=${y} width="200" height=${50 - y}></rect></clipPath>
      </defs>
      <path
        d="M0,${y} H200"
        stroke="var(--wa-color-surface-border)"
        stroke-dasharray="2 3"
      ></path>
      <path d=${points} clip-path="url(#above)" stroke="var(--wa-color-success-on-normal)"></path>
      <path d=${points} clip-path="url(#below)" stroke="var(--wa-color-danger-on-normal)"></path>
    `;
	}
};
customElements.define("sentinel-chart", SentinelChart);
// src/api.js
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
async function postEventStream(path, body, onEvent, { signal } = {}) {
	const response = await fetch(path, {
		method: "POST",
		headers: {
			Accept: "text/event-stream",
			"Content-Type": "application/json"
		},
		body: JSON.stringify(body),
		signal
	});
	if (!response.ok) {
		const payload = await response.json().catch(() => void 0);
		throw new Error(payload?.detail ?? `${response.status} ${response.statusText}`);
	}
	if (!response.body) throw new Error("Chat stream has no response body");
	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";
	try {
		while (true) {
			const { done, value } = await reader.read();
			buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
			const frames = buffer.split("\n\n");
			buffer = frames.pop() ?? "";
			for (const frame of frames) {
				const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
				if (data) await onEvent(JSON.parse(data));
			}
			if (done) break;
		}
	} catch (error) {
		await reader.cancel().catch(() => {});
		throw error;
	} finally {
		reader.releaseLock();
	}
}
// src/live-resource.js
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
// src/format.js
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
// src/modal-utils.js
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
function requestDialog({ label, message, submitLabel, placeholder, danger = false }) {
	return new Promise((resolve) => {
		const container = document.body.appendChild(document.createElement("div"));
		let result;
		D(b`
        <wa-dialog
          class="sentinel-compact-dialog"
          label=${label}
          open
          @wa-after-hide=${(event) => {
			if (event.target !== event.currentTarget) return;
			container.remove();
			resolve(result);
		}}
        >
          <form
            class="wa-stack"
            @submit=${(event) => {
			event.preventDefault();
			const input = container.querySelector("wa-input");
			const value = input?.value?.trim();
			if (input && !value) return;
			result = input ? value : true;
			container.querySelector("wa-dialog").open = false;
		}}
          >
            ${message ? b`<div>${message}</div>` : ""}
            ${placeholder ? b`
                  <wa-input
                    size="small"
                    label="File name"
                    placeholder=${placeholder}
                    required
                    autofocus
                  ></wa-input>
                ` : ""}
            <div class="sentinel-layout">
              <wa-button
                size="small"
                type="button"
                ?autofocus=${!placeholder}
                @click=${() => {
			container.querySelector("wa-dialog").open = false;
		}}
                >Cancel</wa-button
              >
              <wa-button
                size="small"
                type="submit"
                variant=${danger ? "danger" : "brand"}
                >${submitLabel}</wa-button
              >
            </div>
          </form>
        </wa-dialog>
      `, container);
	});
}
// src/sentinel-backtest.js
var phaseLabels = {
	prepare_db: "Preparing database…",
	discover_symbols: "Discovering securities…",
	download_prices: "Downloading historical data…",
	calculate_scores: "Calculating scores…",
	simulate: "Running simulation…"
};
var SentinelBacktest = class extends i$4 {
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
            >Start date&nbsp;<wa-input
              size="small"
              type="date"
              .value=${this.startDate}
              max=${this.endDate}
              required
              @change=${(event) => this.startDate = this.fieldValue(event)}
            ></wa-input
          ></label>
        </div>
        <div>
          <label
            >End date&nbsp;<wa-input
              size="small"
              type="date"
              .value=${this.endDate}
              min=${this.startDate}
              max=${dateInputValue(/* @__PURE__ */ new Date(Date.now() - 864e5))}
              required
              @change=${(event) => this.endDate = this.fieldValue(event)}
            ></wa-input
          ></label>
        </div>
        <div>
          <label
            >Initial capital (EUR)&nbsp;<wa-input
              size="small"
              type="number"
              .value=${this.initialCapital}
              min="100"
              max="10000000"
              step="1000"
              required
              @change=${(event) => this.initialCapital = Number(this.fieldValue(event))}
            ></wa-input
          ></label>
          <div>Starting portfolio value in EUR</div>
        </div>
        <div>
          <label
            >Monthly deposit (EUR)&nbsp;<wa-input
              size="small"
              type="number"
              .value=${this.monthlyDeposit}
              min="0"
              max="100000"
              step="100"
              required
              @change=${(event) => this.monthlyDeposit = Number(this.fieldValue(event))}
            ></wa-input
          ></label>
          <div>Amount to add on the first of each month</div>
        </div>
        <div>
          <label
            >Rebalance frequency&nbsp;<wa-select
              size="small"
              .value=${this.rebalanceFrequency}
              @change=${(event) => this.rebalanceFrequency = this.fieldValue(event)}
            >
              <wa-option value="daily">Daily</wa-option>
              <wa-option value="weekly">Weekly (Recommended)</wa-option>
              <wa-option value="monthly">Monthly</wa-option>
            </wa-select></label
          >
        </div>
        <div aria-hidden="true">&nbsp;</div>
        <wa-card
          ><span slot="header">Securities Selection</span>
          <div>
            <wa-switch
              size="small"
              .checked=${this.useExistingUniverse}
              @change=${(event) => this.useExistingUniverse = event.currentTarget.checked}
              >Use existing universe</wa-switch
            >
          </div>
          <div>Use all active securities from the current database</div>
          ${!this.useExistingUniverse ? b`
                <div>
                  <wa-switch
                    size="small"
                    .checked=${this.pickRandom}
                    @change=${(event) => this.pickRandom = event.currentTarget.checked}
                    >Pick random securities</wa-switch
                  >
                </div>
                ${this.pickRandom ? b`<label
                      >Number of securities&nbsp;<wa-input
                        size="small"
                        type="number"
                        .value=${this.randomCount}
                        min="1"
                        max="100"
                        @change=${(event) => this.randomCount = Number(this.fieldValue(event))}
                      ></wa-input
                    ></label>` : b`<label
                      >Symbols&nbsp;<wa-input
                        size="small"
                        .value=${this.symbols}
                        placeholder="AAPL.US, MSFT.US, GOOGL.US"
                        style="inline-size: 40ch; max-inline-size: 100%"
                        @input=${(event) => this.symbols = this.fieldValue(event)}
                      ></wa-input
                    ></label>`}
              ` : ""}
        </wa-card>
        <div aria-hidden="true">&nbsp;</div>
        <wa-button size="small" type="submit">Run Backtest</wa-button>
      </form>
    `;
	}
	renderRunning() {
		return b`
      <div aria-live="polite">
        <div>${phaseLabels[this.phase] ?? "Starting backtest…"}</div>
        <wa-progress-bar
          label="Backtest progress"
          value=${this.progress}
        ></wa-progress-bar>
        ${this.phase === "download_prices" && this.itemsTotal > 0 ? b`<div>
              ${this.currentItem ? `Processing: ${this.currentItem} · ` : ""}
              ${this.itemsDone} / ${this.itemsTotal} symbols
            </div>` : ""}
        ${this.phase === "simulate" ? b`<div>
              Simulating: ${this.currentDate} ·
              ${Number(this.progress).toFixed(1)}%
            </div>` : ""}
        ${this.portfolioValue > 0 && this.phase === "simulate" ? b`<div>
              Portfolio value: ${formatCurrency(this.portfolioValue, "EUR", 0)}
            </div>` : ""}
        <div aria-hidden="true">&nbsp;</div>
        <wa-button size="small" variant="danger" @click=${this.cancelBacktest}
          >Cancel</wa-button
        >
      </div>
    `;
	}
	renderResult() {
		const values = (this.result?.snapshots ?? []).map((snapshot) => snapshot.total_value);
		return b`
      <div>
        Total invested ${formatCurrency(this.result.total_deposits, "EUR", 0)} ·
        Final value ${formatCurrency(this.result.final_value, "EUR", 0)} ·
        <span data-tone=${this.result.total_return >= 0 ? "success" : "error"}
          >Return ${formatCurrency(this.result.total_return, "EUR", 0)}
          (${formatPercent(this.result.total_return_pct, 2)})</span
        >
      </div>
      <div>
        <span data-tone=${this.result.cagr >= 0 ? "success" : "error"}
          >CAGR ${formatPercent(this.result.cagr, 2)}</span
        >

        <span data-tone="warning"
          >Max drawdown -${formatNumber(this.result.max_drawdown, 2)}%</span
        >
        Sharpe ${formatNumber(this.result.sharpe_ratio, 2)}
      </div>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Equity Curve</span>
        ${values.length > 1 ? b`<sentinel-chart
              role="img"
              height="6"
              aria-label="Backtest equity curve"
              .values=${values}
            ></sentinel-chart>` : "No equity curve data"}
      </wa-card>
      ${this.result.security_performance?.length ? b`
            <div aria-hidden="true">&nbsp;</div>
            <wa-card
              ><span slot="header">Security Performance</span>
              <div style="overflow: auto; min-width: 0">
                <table style="border-collapse: collapse; width: 100%">
                  <thead>
                    <tr>
                      <th style="text-align: left">Symbol</th>
                      <th style="text-align: left">Invested</th>
                      <th style="text-align: left">Final value</th>
                      <th style="text-align: left">Return</th>
                      <th style="text-align: left">Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${this.result.security_performance.map((security) => b`
                        <tr>
                          <td style="text-align: left; vertical-align: top">
                            ${security.symbol}<br />${security.name ?? ""}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${formatCurrency(security.total_invested, "EUR", 0)}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${formatCurrency(security.final_value, "EUR", 0)}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            <span
                              data-tone=${security.total_return >= 0 ? "success" : "error"}
                              >${formatPercent(security.return_pct, 2)}</span
                            >
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${security.num_buys} buys, ${security.num_sells}
                            sells
                          </td>
                        </tr>
                      `)}
                  </tbody>
                </table>
              </div>
            </wa-card>
          ` : ""}
      <div>
        Total trades: ${this.result.trades?.length ?? 0} ·
        <wa-button size="small" @click=${this.reset}
          >Run Another Backtest</wa-button
        >
      </div>
    `;
	}
	render() {
		if (this.status === "running") return this.renderRunning();
		if (this.status === "error") return b`
        <span data-tone="error">Backtest failed: ${this.errorMessage}</span>
        <div>
          <wa-button size="small" @click=${this.reset}>Try Again</wa-button>
        </div>
      `;
		if (this.status === "completed" && this.result) return this.renderResult();
		return this.renderIdle();
	}
};
customElements.define("sentinel-backtest", SentinelBacktest);
// \0vite/preload-helper.js
var scriptRel = "modulepreload";
var assetsURL = function(dep) {
	return "/" + dep;
};
var seen = {};
var isCssPreloadUrl = function isCssPreloadUrl(url) {
	return url.pathname.endsWith(".css");
};
var preloadOnce = function preloadOnce(seen, href, preload) {
	if (href in seen) return seen[href];
	const promise = preload();
	if (!promise) {
		seen[href] = void 0;
		return;
	}
	const preloadPromise = promise.then(() => {
		seen[href] = void 0;
	}, (err) => {
		seen[href] = void 0;
		throw err;
	});
	seen[href] = preloadPromise;
	return preloadPromise;
};
var __vitePreload = function preload(baseModule, deps, importerUrl) {
	let promise = Promise.resolve();
	if (deps && deps.length > 0) {
		let preloadedHrefs;
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
			if (import.meta.resolve) return new URL(import.meta.resolve(specifier));
			return new URL(
				specifier,
				/** #__KEEP__ */
				import.meta.url
			);
		}
		promise = allSettled(deps.map((depString) => {
			depString = assetsURL(depString, importerUrl);
			const dep = importMetaResolve(depString);
			const isCss = isCssPreloadUrl(dep);
			return preloadOnce(seen, dep.href, () => {
				if (preloadedHrefs === void 0) {
					preloadedHrefs = {
						all: /* @__PURE__ */ new Set(),
						styles: /* @__PURE__ */ new Set()
					};
					const links = document.getElementsByTagName("link");
					for (let i = links.length - 1; i >= 0; i--) {
						const link = links[i];
						preloadedHrefs.all.add(link.href);
						if (link.rel === "stylesheet") preloadedHrefs.styles.add(link.href);
					}
				}
				if ((isCss ? preloadedHrefs.styles : preloadedHrefs.all).has(dep.href)) return;
				const link = document.createElement("link");
				link.rel = isCss ? "stylesheet" : scriptRel;
				if (!isCss) link.as = "script";
				link.crossOrigin = "";
				link.href = dep.href;
				if (cspNonce) link.setAttribute("nonce", cspNonce);
				document.head.appendChild(link);
				if (isCss) return new Promise((res, rej) => {
					link.addEventListener("load", res);
					link.addEventListener("error", () => rej(/* @__PURE__ */ new Error(`Unable to preload CSS for ${dep}`)));
				});
			});
		}).filter((p) => p !== void 0));
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
// src/sentinel-code-editor.js
var SentinelCodeEditor = class extends HTMLElement {
	static observedAttributes = [
		"aria-label",
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
		textarea.style.background = "var(--wa-color-surface-default)";
		textarea.style.color = "var(--wa-color-text-normal)";
		textarea.style.fontFamily = "var(--wa-font-family-code)";
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
			const [{ basicSetup, EditorView }, { Compartment, EditorState }, { markdown }, { languages }, { HighlightStyle, LanguageDescription, syntaxHighlighting }, { tags }] = await Promise.all([
				__vitePreload(() => import("./dist-B1JDGwcL.js"), __vite__mapDeps([0,1,2,3,4,5])),
				__vitePreload(() => import("./dist-DgQIi_yG.js").then((n) => n.x), __vite__mapDeps([4,3])),
				__vitePreload(() => import("./dist-DS9RNkCr.js"), __vite__mapDeps([6,4,3,1,2,5,7,8,9,10])),
				__vitePreload(() => import("./dist-Wk6qF9fK.js"), __vite__mapDeps([11,1,2,3,4])),
				__vitePreload(() => import("./dist-BiurrlE2.js"), __vite__mapDeps([1,2,3,4])),
				__vitePreload(() => import("./dist-BvVii4ez.js").then((n) => n.n), __vite__mapDeps([2,3]))
			]);
			if (!this.isConnected || initialization !== this.#initialization) return;
			const languageCompartment = new Compartment();
			const editableCompartment = new Compartment();
			const readOnlyCompartment = new Compartment();
			const ariaCompartment = new Compartment();
			const initialLanguageKey = this.#languageKey();
			const languageExtension = await this.#loadLanguageExtension({
				LanguageDescription,
				languages,
				markdown
			});
			if (!this.isConnected || initialization !== this.#initialization) return;
			const layoutTheme = EditorView.theme({
				"&": {
					height: "100%",
					maxWidth: "100%",
					fontSize: "inherit",
					backgroundColor: "var(--wa-color-surface-default)",
					color: "var(--wa-color-text-normal)",
					border: "var(--wa-border-width-s) solid var(--wa-color-surface-border)",
					borderRadius: "var(--wa-border-radius-s)"
				},
				".cm-scroller": {
					height: "100%",
					fontFamily: "var(--wa-font-family-code)",
					lineHeight: "inherit",
					overflow: "auto"
				},
				".cm-content": { padding: "0" },
				".cm-line": { padding: "0 1ch" },
				".cm-gutters": {
					border: "0",
					backgroundColor: "var(--wa-color-surface-lowered)",
					color: "var(--wa-color-text-quiet)"
				},
				".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--wa-color-text-normal)" },
				"& .cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "var(--wa-color-brand-fill-normal)" },
				".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "transparent" },
				"&.cm-focused": {
					outline: "var(--wa-focus-ring)",
					outlineOffset: "calc(-1 * var(--wa-focus-ring-width))"
				}
			});
			const highlighting = syntaxHighlighting(HighlightStyle.define([
				{
					tag: [tags.keyword, tags.operatorKeyword],
					color: "var(--wa-color-brand-on-quiet)"
				},
				{
					tag: [tags.string, tags.regexp],
					color: "var(--wa-color-success-on-quiet)"
				},
				{
					tag: [
						tags.number,
						tags.bool,
						tags.null
					],
					color: "var(--wa-color-warning-on-quiet)"
				},
				{
					tag: tags.comment,
					color: "var(--wa-color-text-quiet)",
					fontStyle: "italic"
				},
				{
					tag: [tags.heading, tags.strong],
					fontWeight: "bold"
				}
			]));
			const runtime = {
				EditorState,
				EditorView,
				LanguageDescription,
				languages,
				markdown,
				languageCompartment,
				editableCompartment,
				readOnlyCompartment,
				ariaCompartment,
				languageExtension,
				languageKey: initialLanguageKey,
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
					highlighting,
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
// src/sentinel-tasks.js
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
var SentinelTasks = class extends i$4 {
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
		actionError: { state: true }
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
		return requestDialog({
			label: "Discard changes",
			message: `Discard unsaved changes to "${this.task?.name || this.selectedId}"?`,
			submitLabel: "Discard",
			danger: true
		});
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
		if (!force && !await this.confirmClose()) return;
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
		const selectedId = this.selectedId;
		try {
			const runs = await getJson(`/api/tasks/${encodeURIComponent(selectedId)}/runs?limit=50`);
			if (this.selectedId !== selectedId) return;
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
		const task = this.task;
		if (!task || !await requestDialog({
			label: "Delete task",
			message: `Delete task "${task.name}"?`,
			submitLabel: "Delete",
			danger: true
		})) return;
		this.busyAction = "delete-task";
		try {
			await deleteJson(`/api/tasks/${encodeURIComponent(task.id)}`);
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
	async createFile() {
		const name = await requestDialog({
			label: "New file",
			placeholder: "prompt.md",
			submitLabel: "Create"
		});
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
		if (!await requestDialog({
			label: "Delete file",
			message: `Permanently delete "${file.name}"?`,
			submitLabel: "Delete",
			danger: true
		})) return;
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
      <wa-card
        ><span slot="header">Tasks</span>
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
                  ><wa-button
                    size="small"
                    @click=${() => this.selectTask(task.id)}
                    >${task.name}</wa-button
                  >
                  <span
                    data-tone=${task.invalid ? "error" : task.enabled ? "success" : ""}
                    >${task.invalid ? "invalid" : task.enabled ? "on" : "off"}</span
                  >
                  <div>${task.id}</div>
                </div>
              `)}
          `)}
      </wa-card>
    `;
	}
	renderToolbar() {
		return b`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>
          ${this.task.name}
          ${this.dirty ? b`<span data-tone="warning">unsaved</span>` : ""} ·
          ${this.task.source} · ${this.task.id}
        </span>
        <span>
          <wa-button
            size="small"
            ?disabled=${this.dirty || this.running || this.busyAction !== ""}
            @click=${this.validateTask}
            >Check</wa-button
          >
          ${this.running ? b`<wa-button
                size="small"
                variant="danger"
                @click=${this.stopRun}
                >Stop</wa-button
              >` : b`<wa-button
                size="small"
                ?disabled=${this.dirty || this.task.invalid || this.busyAction !== ""}
                @click=${this.startRun}
                >Run</wa-button
              >`}
          <wa-button
            size="small"
            variant="danger"
            ?disabled=${this.running || this.task.source === "core" || this.busyAction !== ""}
            @click=${this.deleteTask}
            >Delete</wa-button
          >
        </span>
      </div>
    `;
	}
	renderFiles() {
		const active = this.files.find((file) => file.name === this.activeFile);
		const draft = this.activeFile ? this.drafts[this.activeFile] ?? "" : "";
		const dirty = this.activeFile && this.activeFile in this.baselines && draft !== this.baselines[this.activeFile];
		return b`
      <div class="sentinel-layout" data-align="start" data-wrap>
        <wa-card style="flex: 1 1 20ch; min-width: 0"
          ><span slot="header">Files</span>
          <div>
            <wa-button size="small" @click=${this.createFile}
              >New File</wa-button
            >
          </div>
          ${this.files.map((file) => b`
              <div>
                <span aria-hidden="true"
                  >${file.name === this.activeFile ? "▶" : " "}&nbsp;</span
                ><wa-button
                  size="small"
                  @click=${() => this.selectFile(file.name)}
                  >${file.name}</wa-button
                >
                ${this.drafts[file.name] !== this.baselines[file.name] && file.name in this.baselines ? b`<span data-tone="warning">unsaved</span>` : ""}
                ${file.protected ? "protected" : ""}
                ${!file.protected ? b`<wa-button
                      size="small"
                      variant="danger"
                      ?disabled=${this.running}
                      @click=${() => this.deleteFile(file)}
                      >Delete</wa-button
                    >` : ""}
              </div>
            `)}
        </wa-card>
        <section style="flex: 4 1 60ch; min-width: 0">
          <div>
            ${this.activeFile ?? "No file selected"}
            ${active?.protected ? "· protected" : ""}
            ${dirty ? b`· <span data-tone="warning">unsaved</span>` : ""}
            <wa-button
              size="small"
              ?disabled=${!dirty || this.running || this.busyAction !== ""}
              @click=${this.saveFile}
              >Save</wa-button
            >
          </div>
          <sentinel-code-editor
            aria-label="${this.activeFile ?? "Task file"} content"
            document-id="${this.selectedId ?? ""}/${this.activeFile ?? ""}"
            filename=${this.activeFile ?? "file.txt"}
            language=${active?.language ?? "plaintext"}
            .value=${draft}
            ?disabled=${!this.activeFile || this.running}
            @input=${(event) => this.updateDraft(event.currentTarget.value)}
          ></sentinel-code-editor>
        </section>
      </div>
    `;
	}
	renderSchedule() {
		const parts = this.intervalParts();
		return b`
      <div>Schedule</div>
      <wa-radio-group
        size="small"
        aria-label="Task schedule mode"
        .value=${this.scheduleMode}
        ?disabled=${this.running}
        @change=${(event) => this.setScheduleMode(event.currentTarget.value)}
      >
        <wa-radio appearance="button" value="off">Off</wa-radio>
        <wa-radio appearance="button" value="cron">Cron</wa-radio>
        <wa-radio appearance="button" value="interval">Interval</wa-radio>
      </wa-radio-group>
      ${this.scheduleMode === "cron" ? b`
            <div>
              <label
                >Cron&nbsp;<wa-input
                  size="small"
                  .value=${this.metadata.schedule ?? defaultCron}
                  style="inline-size: 24ch; max-inline-size: 100%"
                  ?disabled=${this.running}
                  @input=${(event) => this.patchMetadata({ schedule: event.currentTarget.value || defaultCron })}
                ></wa-input
              ></label>
            </div>
            ${cronFields.map((field) => {
			const selected = this.cronValues(field.index);
			return b`
                <div>${field.label}</div>
                <div class="sentinel-layout" data-align="baseline" data-wrap>
                  ${field.options.map(([value, label]) => b`
                      <wa-switch
                        size="small"
                        .checked=${selected.has(value)}
                        ?disabled=${this.running}
                        @change=${(event) => this.toggleCronValue(field.index, value, event.currentTarget.checked)}
                        >${value} ${label}</wa-switch
                      ><span aria-hidden="true">&nbsp;</span>
                    `)}
                </div>
              `;
		})}
          ` : ""}
      ${this.scheduleMode === "interval" ? b`
            <div class="sentinel-layout" data-align="baseline" data-wrap>
              <label
                >Days&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="0"
                  .value=${parts.days}
                  @change=${(event) => this.patchInterval("days", event.currentTarget.value)}
                ></wa-input
              ></label>

              <label
                >Hours&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="0"
                  max="23"
                  .value=${parts.hours}
                  @change=${(event) => this.patchInterval("hours", event.currentTarget.value)}
                ></wa-input
              ></label>

              <label
                >Minutes&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="0"
                  max="59"
                  .value=${parts.minutes}
                  @change=${(event) => this.patchInterval("minutes", event.currentTarget.value)}
                ></wa-input
              ></label>

              <label
                >Run when&nbsp;<wa-select
                  size="small"
                  .value=${this.metadata.schedulePolicy?.runWhen ?? "idle"}
                  @change=${(event) => this.patchSchedulePolicy({ runWhen: event.currentTarget.value })}
                >
                  <wa-option value="idle">Idle</wa-option>
                  <wa-option value="immediate">Immediate</wa-option>
                </wa-select></label
              >

              <label
                >Priority&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="-1000"
                  max="1000"
                  .value=${this.metadata.schedulePolicy?.priority ?? 0}
                  @change=${(event) => this.patchSchedulePolicy({ priority: Number(event.currentTarget.value) })}
                ></wa-input
              ></label>
            </div>
          ` : ""}
    `;
	}
	renderMetadata() {
		if (!this.metadata) return b`<div>Loading metadata…</div>`;
		return b`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>Metadata</span>
        <wa-button
          size="small"
          ?disabled=${!this.metadataDirty || this.running || this.busyAction !== ""}
          @click=${this.saveMetadata}
          >Save</wa-button
        >
      </div>
      <div>
        <label
          ><span>Name</span>
          <wa-input
            size="small"
            style="inline-size: 100%"
            .value=${this.metadata.name}
            @input=${(event) => this.patchMetadata({ name: event.currentTarget.value })}
          ></wa-input
        ></label>
        <wa-switch
          size="small"
          .checked=${this.metadata.enabled}
          ?disabled=${this.running}
          @change=${(event) => this.patchMetadata({ enabled: event.currentTarget.checked })}
          >Enabled</wa-switch
        >
      </div>
      <div>
        <label>Description</label>
        <wa-textarea
          size="small"
          aria-label="Task description"
          style="inline-size: 100%"
          rows="4"
          .value=${this.metadata.description}
          ?disabled=${this.running}
          @input=${(event) => this.patchMetadata({ description: event.currentTarget.value })}
        ></wa-textarea>
      </div>
      <div>
        <label
          ><span>Tags</span>
          <wa-input
            size="small"
            style="inline-size: 100%"
            .value=${this.metadata.tags.join(", ")}
            ?disabled=${this.running}
            @input=${(event) => this.patchMetadata({ tags: event.currentTarget.value.split(",").map((tag) => tag.trim()).filter(Boolean) })}
          ></wa-input
        ></label>
      </div>
      <div>
        <label
          >Timeout (seconds)&nbsp;<wa-input
            size="small"
            type="number"
            min="0"
            step="60"
            .value=${this.metadata.timeout}
            ?disabled=${this.running}
            @change=${(event) => this.patchMetadata({ timeout: Number(event.currentTarget.value) })}
          ></wa-input
        ></label>
      </div>
      <div>
        <label
          ><span>Working directory</span>
          <wa-input
            size="small"
            style="inline-size: 100%"
            .value=${this.metadata.cwd}
            placeholder="@/tasks/artifacts/{{task-id}}"
            ?disabled=${this.running}
            @input=${(event) => this.patchMetadata({ cwd: event.currentTarget.value })}
          ></wa-input
        ></label>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderSchedule()}
    `;
	}
	renderRun() {
		return b`
      <wa-card
        ><span slot="header">Run</span>
        <div>
          Status
          <span data-tone=${statusVariant(this.run?.status) || ""}
            >${this.run?.status ?? "idle"}</span
          >
        </div>
        <div>History</div>
        ${this.runs.length ? this.runs.map((run) => b`
                <div>
                  <span aria-hidden="true"
                    >${run.id === this.runId ? "▶" : " "}&nbsp;</span
                  ><wa-button size="small" @click=${() => this.loadRun(run.id)}
                    >${run.status} -
                    ${run.createdAt ? formatDateTime(run.createdAt) : run.id}</wa-button
                  >
                </div>
              `) : "No runs"}
        <div>Inputs (JSON)</div>
        <wa-textarea
          size="small"
          aria-label="Task run inputs"
          style="inline-size: 100%"
          rows="4"
          .value=${this.runInputs}
          ?disabled=${this.running}
          @input=${(event) => this.runInputs = event.currentTarget.value}
        ></wa-textarea>
        <div>Log</div>
        ${(this.run?.log ?? []).map((line) => b`<div><code>${line}</code></div>`)}
        ${this.run?.error ? b`<span data-tone="error">${this.run.error}</span>` : ""}
        <pre style="white-space: pre-wrap; overflow-wrap: anywhere">
${this.run?.liveOutput ?? " "}</pre
        >
      </wa-card>
    `;
	}
	renderWorkbench() {
		if (this.loading && !this.task) return b`<div>Loading task…</div>`;
		if (!this.task) return b`<div>No task selected</div>`;
		return b`
      ${this.renderToolbar()}
      ${this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError ? b`<span data-tone="error">${this.actionError}</span>` : ""}
      <div aria-hidden="true">&nbsp;</div>
      <div class="sentinel-layout" data-align="start" data-wrap>
        <section style="flex: 3 1 60ch; min-width: 0">
          <wa-radio-group
            size="small"
            aria-label="Task editor view"
            .value=${this.tab}
            @change=${(event) => this.tab = event.currentTarget.value}
          >
            <wa-radio appearance="button" value="files">Files</wa-radio>
            <wa-radio appearance="button" value="metadata">Metadata</wa-radio>
          </wa-radio-group>
          ${this.tab === "metadata" ? this.renderMetadata() : this.renderFiles()}
        </section>
        <aside style="flex: 1 1 32ch; min-width: 0">${this.renderRun()}</aside>
      </div>
    `;
	}
	render() {
		return b`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>${this.tasks.length} core and user task definitions</span>
        <span>
          <wa-button
            size="small"
            ?disabled=${this.busyAction !== ""}
            @click=${this.createTask}
            >New</wa-button
          >
          <wa-button size="small" @click=${() => this.loadTasks()}
            >Refresh</wa-button
          >
        </span>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.loading && this.tasks.length === 0 ? b`<div>Loading tasks…</div>` : b`
            <div class="sentinel-layout" data-align="start" data-wrap>
              <aside style="flex: 1 1 24ch; min-width: 0">
                ${this.renderTaskList()}
              </aside>
              <section style="flex: 4 1 70ch; min-width: 0">
                ${this.renderWorkbench()}
              </section>
            </div>
          `}
    `;
	}
};
customElements.define("sentinel-tasks", SentinelTasks);
// src/sentinel-research.js
var SentinelResearch = class extends i$4 {
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
		artifactError: { state: true },
		chatMessages: { state: true },
		chatDraft: { state: true },
		chatBusy: { state: true },
		chatError: { state: true }
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
		this.chatMessages = this.loadChatMessages();
		this.chatDraft = "";
		this.chatBusy = false;
		this.chatError = "";
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
	loadChatMessages() {
		try {
			const storageKey = "sentinel-research-chat";
			const stored = window.localStorage.getItem(storageKey);
			const legacy = window.sessionStorage.getItem(storageKey);
			const value = JSON.parse(stored ?? legacy ?? "[]");
			if (stored === null && legacy !== null) {
				window.localStorage.setItem(storageKey, legacy);
				window.sessionStorage.removeItem(storageKey);
			}
			return Array.isArray(value) ? value.filter((entry) => ["user", "assistant"].includes(entry?.role) && typeof entry?.content === "string").map((entry) => ({
				...entry,
				pending: false
			})) : [];
		} catch {
			return [];
		}
	}
	persistChatMessages() {
		try {
			window.localStorage.setItem("sentinel-research-chat", JSON.stringify(this.chatMessages));
		} catch {}
	}
	clearChat() {
		this.chatMessages = [];
		this.chatError = "";
		this.persistChatMessages();
		window.sessionStorage.removeItem("sentinel-research-chat");
	}
	chatHistory() {
		return this.chatMessages.filter((entry) => ["user", "assistant"].includes(entry.role) && typeof entry.content === "string" && !entry.pending).map((entry) => ({
			role: entry.role,
			content: entry.contextContent || entry.content
		}));
	}
	updateStreamingAssistant(id, update) {
		const transcript = this.querySelector("[data-research-chat-transcript]");
		const follow = !transcript || transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 48;
		this.chatMessages = this.chatMessages.map((entry) => entry.id === id ? update(entry) : entry);
		this.persistChatMessages();
		if (follow) this.scrollChatToEnd();
	}
	handleChatEvent(id, event) {
		if (event.type === "error") throw new Error(event.error || "Chat failed");
		this.updateStreamingAssistant(id, (entry) => {
			if (event.type === "content_delta") {
				const segments = [...entry.segments ?? []];
				const index = segments.findIndex((segment) => segment.turnId === event.turn_id);
				if (index === -1) segments.push({
					turnId: event.turn_id,
					content: event.delta
				});
				else segments[index] = {
					...segments[index],
					content: segments[index].content + event.delta
				};
				return {
					...entry,
					segments,
					content: segments.map((segment) => segment.content).join("")
				};
			}
			if (event.type === "reasoning_delta") {
				const reasoning = [...entry.reasoning ?? []];
				const index = reasoning.findIndex((item) => item.turnId === event.turn_id);
				if (index === -1) reasoning.push({
					turnId: event.turn_id,
					content: event.delta
				});
				else reasoning[index] = {
					...reasoning[index],
					content: reasoning[index].content + event.delta
				};
				return {
					...entry,
					reasoning
				};
			}
			if (event.type === "turn_reset") {
				const segments = (entry.segments ?? []).filter((segment) => segment.turnId !== event.turn_id);
				return {
					...entry,
					segments,
					content: segments.map((segment) => segment.content).join(""),
					reasoning: (entry.reasoning ?? []).filter((item) => item.turnId !== event.turn_id)
				};
			}
			if (event.type === "tool_start") return {
				...entry,
				tools: [...entry.tools ?? [], {
					id: event.id,
					name: event.name,
					arguments: event.arguments,
					result: "",
					status: "running"
				}]
			};
			if (event.type === "tool_result") return {
				...entry,
				tools: (entry.tools ?? []).map((tool) => tool.id === event.id ? {
					...tool,
					result: event.result,
					status: "complete"
				} : tool)
			};
			if (event.type === "context") return {
				...entry,
				context: event
			};
			if (event.type === "done") return {
				...entry,
				content: entry.content || event.output || "",
				contextContent: event.output || entry.content || "",
				pending: false
			};
			return entry;
		});
	}
	async sendChatMessage() {
		const message = this.chatDraft.trim();
		if (!message || this.chatBusy) return;
		const history = this.chatHistory();
		const assistantId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
		this.chatMessages = [
			...this.chatMessages,
			{
				role: "user",
				content: message
			},
			{
				id: assistantId,
				role: "assistant",
				content: "",
				contextContent: "",
				segments: [],
				reasoning: [],
				tools: [],
				pending: true
			}
		];
		this.chatDraft = "";
		this.chatBusy = true;
		this.chatError = "";
		this.persistChatMessages();
		await this.scrollChatToEnd();
		try {
			await postEventStream("/api/ai/chat", {
				message,
				history
			}, (event) => this.handleChatEvent(assistantId, event));
		} catch (error) {
			this.chatError = error.message;
			this.updateStreamingAssistant(assistantId, (entry) => ({
				...entry,
				pending: false
			}));
		} finally {
			this.chatBusy = false;
			await this.scrollChatToEnd();
			this.querySelector("[data-research-chat-input]")?.focus();
		}
	}
	async scrollChatToEnd() {
		await this.updateComplete;
		const transcript = this.querySelector("[data-research-chat-transcript]");
		if (transcript) transcript.scrollTop = transcript.scrollHeight;
	}
	handleChatKeydown(event) {
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault();
			this.sendChatMessage();
		}
	}
	formatToolArguments(value) {
		try {
			return JSON.stringify(JSON.parse(value), null, 2);
		} catch {
			return value;
		}
	}
	changeUnitsFilter(name, value) {
		this[name] = value;
		this.units.refresh();
	}
	async changeTab(event) {
		const control = event.currentTarget;
		const nextTab = control.value;
		if (this.tab === "tasks" && nextTab !== "tasks") {
			const tasks = this.querySelector("sentinel-tasks");
			if (tasks?.dirty && !await tasks.confirmClose()) {
				control.value = "tasks";
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
        Securities ${security.stale}/${security.total} stale · Queued
        ${status.queued?.length ?? 0} · Memory ${status.memory?.findings ?? "-"}
        findings
      </div>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Current Work</span>
        ${status.running ? b`
              <div>${status.running.label}</div>
              <div>${status.running.kind}:${status.running.key}</div>
              ${status.running.elapsed_seconds !== void 0 ? b`<div>
                    ${formatDuration(status.running.elapsed_seconds * 1e3)}
                  </div>` : ""}
            ` : "Idle"}
      </wa-card>
      <div aria-hidden="true">&nbsp;</div>
      <div class="sentinel-layout" data-align="start" data-wrap>
        <wa-card style="flex: 1 1 40ch; min-width: 0"
          ><span slot="header">Next in Line</span>
          ${status.queued?.length ? status.queued.map((item) => b`
                  <div>
                    ${item.unit_label ?? `${item.unit_kind}:${item.unit_key}`} ·
                    ${item.task_name ?? item.task_id ?? item.kind}
                  </div>
                `) : "Queue empty"}
        </wa-card>
        <wa-card style="flex: 1 1 40ch; min-width: 0"
          ><span slot="header">Latest Tick</span>
          ${status.last_run ? b`
                <div>
                  <span data-tone=${statusVariant(status.last_run.status) || ""}
                    >${status.last_run.status}</span
                  >
                  · ${formatRelativeTime(status.last_run.finished_at)}
                </div>
                ${status.last_run.unit_label ? b`<div>
                      ${status.last_run.unit_label}
                      ${status.last_run.unit_key ? `(${status.last_run.unit_key})` : ""}
                    </div>` : ""}
                ${status.last_run.duration_seconds !== void 0 ? b`<div>
                      ${formatDuration(status.last_run.duration_seconds * 1e3)}
                    </div>` : ""}
                ${status.last_run.error ? b`<span data-tone="error"
                      >${status.last_run.error}</span
                    >` : ""}
              ` : "No runs yet"}
        </wa-card>
      </div>
      ${status.staleness?.most_stale ? b`<div>
            Oldest: ${status.staleness.most_stale.label}
            (${status.staleness.most_stale.kind})
          </div>` : ""}
      ${status.memory?.error ? b`<span data-tone="error">Memory: ${status.memory.error}</span>` : ""}
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Manual Rating</span>
        <div class="sentinel-layout" data-align="baseline" data-wrap>
          <label
            >Security&nbsp;<wa-select
              size="small"
              .value=${this.ratingSymbol}
              @change=${(event) => this.ratingSymbol = event.currentTarget.value}
            >
              <wa-option value="">Select a security</wa-option>
              ${securities.map((unit) => b`<wa-option value=${unit.key}>
                    ${unit.label} (${unit.key})
                  </wa-option>`)}
            </wa-select></label
          >
          <span aria-hidden="true">&nbsp;</span>
          <wa-button
            size="small"
            ?disabled=${!this.ratingSymbol || this.busy}
            @click=${() => this.requestResearch("rate", "security", this.ratingSymbol)}
            >Rate now</wa-button
          >
        </div>
      </wa-card>
    `;
	}
	renderUnits() {
		const units = this.units.value?.units ?? [];
		return b`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <label
          >Kind&nbsp;<wa-select
            size="small"
            .value=${this.kind}
            @change=${(event) => this.changeUnitsFilter("kind", event.currentTarget.value)}
          >
            <wa-option value="">All units</wa-option>
            <wa-option value="security">Securities</wa-option>
            <wa-option value="portfolio">Portfolio</wa-option>
          </wa-select></label
        >

        <wa-switch
          size="small"
          .checked=${this.staleOnly}
          @change=${(event) => this.changeUnitsFilter("staleOnly", event.currentTarget.checked)}
          >Stale only</wa-switch
        >

        <wa-button size="small" @click=${this.refreshAll}>Refresh</wa-button>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.units.loading && !this.units.value ? "Loading units…" : units.length === 0 ? "No research units match this view." : b`
              <div style="overflow: auto; min-width: 0">
                <table style="border-collapse: collapse; width: 100%">
                  <thead>
                    <tr>
                      <th style="text-align: left">Unit</th>
                      <th style="text-align: left">Kind</th>
                      <th style="text-align: left">Last analyzed</th>
                      <th style="text-align: left">State</th>
                      <th style="text-align: left">Error</th>
                      <th style="text-align: left">Actions</th>
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
                            ${unit.kind}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${unit.last_analyzed_at ? formatRelativeTime(unit.last_analyzed_at) : "Never"}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            <span data-tone=${statusVariant(state) || ""}
                              >${state}</span
                            >
                          </td>
                          <td
                            style="text-align: left; vertical-align: top; max-width: 40ch; overflow-wrap: anywhere"
                          >
                            ${unit.last_error ?? "-"}
                          </td>
                          <td
                            style="text-align: left; vertical-align: top; white-space: nowrap"
                          >
                            ${unit.kind !== "portfolio" ? b`<wa-button
                                  size="small"
                                  ?disabled=${this.busy || unit.status === "running"}
                                  @click=${() => this.requestResearch("analyze", unit.kind, unit.key)}
                                  >Analyze</wa-button
                                >` : ""}
                            <wa-button
                              size="small"
                              ?disabled=${!unit.artifacts?.length}
                              @click=${() => this.openArtifacts(unit)}
                              >View</wa-button
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
              <th style="text-align: left">Status</th>
              <th style="text-align: left">Duration</th>
              <th style="text-align: left">Finished</th>
              <th style="text-align: left">Error</th>
            </tr>
          </thead>
          <tbody>
            ${history.map((entry) => b`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${entry.unit_label ?? entry.unit_key ?? entry.job_id?.replace("ai:tick:", "") ?? "-"}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    <span data-tone=${statusVariant(entry.status) || ""}
                      >${entry.status}</span
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatDuration(entry.duration_ms)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatRelativeTime(typeof entry.executed_at === "number" ? entry.executed_at * 1e3 : entry.executed_at)}
                  </td>
                  <td
                    style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
                  >
                    ${entry.error ?? "-"}
                  </td>
                </tr>
              `)}
          </tbody>
        </table>
      </div>
    `;
	}
	renderChat() {
		return b`
      <section
        data-research-chat-transcript
        aria-label="Research chat transcript"
        aria-live="polite"
        style="height: min(52vh, 36rem); overflow-y: auto; padding-right: 1ch"
      >
        ${this.chatMessages.length ? this.chatMessages.map((message) => b`
                <article style="margin-bottom: 1.25rem">
                  <div>
                    <span
                      >${message.role === "assistant" ? "Sentinel" : "You"}</span
                    >
                  </div>
                  <div
                    style="white-space: pre-wrap; overflow-wrap: anywhere; max-width: 78ch"
                  >
                    ${message.content}
                  </div>
                  ${message.role === "assistant" ? b`
                        ${(message.reasoning ?? []).map((item, index) => b`
                            <wa-details
                              style="margin-top: 0.45rem; max-width: 78ch"
                            >
                              <span slot="summary">
                                Reasoning${message.reasoning.length > 1 ? ` ${index + 1}` : ""}
                              </span>
                              <div
                                style="white-space: pre-wrap; overflow-wrap: anywhere; padding: 0.4rem 0 0 2ch"
                              >
                                ${item.content}
                              </div>
                            </wa-details>
                          `)}
                        ${(message.tools ?? []).map((tool) => b`
                            <wa-details
                              style="margin-top: 0.45rem; max-width: 78ch"
                            >
                              <span slot="summary">
                                Tool · ${tool.name} ·
                                ${tool.status === "complete" ? "complete" : "running"}
                              </span>
                              <div style="padding: 0.4rem 0 0 2ch">
                                <div>Arguments</div>
                                <pre
                                  style="white-space: pre-wrap; overflow-wrap: anywhere; margin: 0.25rem 0 0.75rem"
                                >
${this.formatToolArguments(tool.arguments)}</pre
                                >
                                <div>Result</div>
                                <pre
                                  style="white-space: pre-wrap; overflow-wrap: anywhere; margin: 0.25rem 0 0"
                                >
${tool.result || "Waiting…"}</pre
                                >
                              </div>
                            </wa-details>
                          `)}
                        ${message.context?.dropped_messages > 0 ? b`
                              <wa-details
                                style="margin-top: 0.45rem; max-width: 78ch"
                              >
                                <span slot="summary">
                                  Context · ${message.context.dropped_messages}
                                  older messages omitted
                                </span>
                                <div style="padding: 0.4rem 0 0 2ch">
                                  The newest
                                  ${message.context.retained_messages} messages
                                  were retained inside the
                                  ${Math.round(message.context.limit_tokens / 1024)}k-token
                                  context window.
                                </div>
                              </wa-details>
                            ` : ""}
                      ` : ""}
                </article>
              `) : b`<div style="max-width: 68ch">
              Ask about the research pipeline, inspect any generated artifact,
              search the web, browse with Firefox, or operate Sentinel directly.
            </div>`}
        ${this.chatBusy ? b`<div>Streaming…</div>` : ""}
      </section>
      <wa-divider></wa-divider>
      <label for="research-chat-input">Message</label>
      <wa-textarea
        size="small"
        id="research-chat-input"
        data-research-chat-input
        aria-label="Message research chat"
        style="inline-size: 100%"
        rows="4"
        placeholder="Ask Sentinel…"
        .value=${this.chatDraft}
        ?disabled=${this.chatBusy}
        @input=${(event) => this.chatDraft = event.currentTarget.value}
        @keydown=${this.handleChatKeydown}
      ></wa-textarea>
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>Enter sends · Shift+Enter adds a line</span>
        <span>
          <wa-button
            size="small"
            ?disabled=${this.chatMessages.length === 0 || this.chatBusy}
            @click=${this.clearChat}
            >Clear</wa-button
          >
          <wa-button
            size="small"
            ?disabled=${!this.chatDraft.trim() || this.chatBusy}
            @click=${this.sendChatMessage}
            >Send</wa-button
          >
        </span>
      </div>
      ${this.chatError ? b`<span data-tone="error">${this.chatError}</span>` : ""}
    `;
	}
	renderArtifactModal() {
		const unit = this.artifactUnit;
		if (!unit) return "";
		return b`
      <wa-dialog
        label="${unit.label} / artifacts"
        open
        @wa-after-hide=${(event) => {
			if (event.target === event.currentTarget) this.closeArtifacts();
		}}
      >
        ${unit.artifacts?.length ? b`
              <label
                >Artifact&nbsp;<wa-select
                  size="small"
                  .value=${this.activeArtifact}
                  @change=${(event) => this.changeArtifact(event.currentTarget.value)}
                >
                  ${unit.artifacts.map((name) => b`<wa-option value=${name}>${name}</wa-option>`)}
                </wa-select></label
              >
              <div aria-hidden="true">&nbsp;</div>
              ${this.artifactLoading ? "Loading artifact…" : this.artifactError ? b`<span data-tone="error">${this.artifactError}</span>` : b`<pre
                      style="white-space: pre-wrap; overflow-wrap: anywhere"
                    >
${this.artifactContent}</pre
                    >`}
            ` : "No artifacts have been written for this unit."}
      </wa-dialog>
    `;
	}
	render() {
		const error = this.status.error ?? this.units.error ?? this.allUnits.error ?? this.history.error;
		const loading = !this.status.value && this.status.loading || !this.allUnits.value && this.allUnits.loading;
		const enabled = this.status.value?.enabled;
		const pipelineState = loading ? b`<span>loading</span>` : error && !this.status.value ? b`<span data-tone="error">unavailable</span>` : b`<span data-tone=${enabled ? "success" : ""}
            >${enabled ? "enabled" : "paused"}</span
          >`;
		let content;
		if (this.tab === "tasks") content = b`<sentinel-tasks></sentinel-tasks>`;
		else if (this.tab === "chat") content = this.renderChat();
		else if (loading) content = b`<div>Loading research pipeline…</div>`;
		else if (error && !this.status.value) content = b`<span data-tone="error">${error.message}</span>`;
		else if (this.tab === "units") content = this.renderUnits();
		else if (this.tab === "history") content = this.renderHistory();
		else content = this.renderStatus();
		return b`
      <div>Pipeline ${pipelineState}</div>
      <wa-radio-group
        size="small"
        aria-label="Research pipeline view"
        .value=${this.tab}
        @change=${this.changeTab}
      >
        <wa-radio appearance="button" value="status">Status</wa-radio>
        <wa-radio appearance="button" value="units">Units</wa-radio>
        <wa-radio appearance="button" value="history">History</wa-radio>
        <wa-radio appearance="button" value="chat">Chat</wa-radio>
        <wa-radio appearance="button" value="tasks">Tasks</wa-radio>
      </wa-radio-group>
      <div aria-hidden="true">&nbsp;</div>
      ${content}
      ${this.tab !== "tasks" && this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.tab !== "tasks" && this.actionError ? b`<span data-tone="error">${this.actionError}</span>` : ""}
      ${this.renderArtifactModal()}
    `;
	}
};
customElements.define("sentinel-research", SentinelResearch);
// src/sentinel-scheduler.js
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
var SentinelScheduler = class extends i$4 {
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
        >${label}&nbsp;<wa-input
          size="small"
          type="number"
          min="1"
          max="10080"
          .value=${display.value}
          ?disabled=${this.busyAction !== ""}
          @change=${(event) => this.updateInterval(job, field, event.currentTarget.value, display.unit)}
        ></wa-input
      ></label>
      <wa-select
        size="small"
        aria-label="${label} unit for ${job.job_type}"
        .value=${display.unit}
        ?disabled=${this.busyAction !== ""}
        @change=${(event) => this.updateInterval(job, field, display.value, event.currentTarget.value)}
      >
        <wa-option value="minutes">Minutes</wa-option>
        <wa-option value="hours">Hours</wa-option>
        <wa-option value="days">Days</wa-option>
      </wa-select>
    `;
	}
	renderStatus() {
		const status = this.status.value ?? {};
		return b`
      <wa-card
        ><span slot="header">Currently Running</span>
        ${status.current ?? "No job running"}
      </wa-card>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Upcoming Jobs</span>
        ${status.upcoming?.length ? status.upcoming.map((job) => b`
                <div>${job.job_type} · ${formatRelativeTime(job.next_run)}</div>
              `) : "No upcoming jobs"}
      </wa-card>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Recent Jobs</span>
        ${status.recent?.length ? status.recent.map((job) => b`
                <div>
                  ${job.job_type} ·
                  <span data-tone=${statusVariant(job.status) || ""}
                    >${job.status}</span
                  >
                  · ${formatRelativeTime(job.executed_at)}
                </div>
              `) : "No recent jobs"}
      </wa-card>
    `;
	}
	renderJob(job) {
		const busy = this.busyAction !== "";
		return b`
      <div>
        <div
          class="sentinel-layout"
          data-align="baseline"
          data-justify="between"
          data-wrap
        >
          <span>
            ${job.job_type}
            ${job.last_status ? b`<span data-tone=${statusVariant(job.last_status) || ""}
                  >${job.last_status}</span
                >` : ""}
          </span>
          <span>
            <label
              >Timing&nbsp;<wa-select
                size="small"
                .value=${String(job.market_timing)}
                ?disabled=${busy}
                @change=${(event) => this.updateSchedule(job.job_type, { market_timing: Number(event.currentTarget.value) })}
              >
                <wa-option value="0">Any time</wa-option>
                <wa-option value="1">After close</wa-option>
                <wa-option value="2">During open</wa-option>
                <wa-option value="3">All closed</wa-option>
              </wa-select></label
            >
            <wa-button
              size="small"
              ?disabled=${busy}
              @click=${() => this.runJob(job.job_type)}
              >${this.busyAction === `run:${job.job_type}` ? "Running…" : "Run"}</wa-button
            >
          </span>
        </div>
        <div>${job.description ?? ""}</div>
        <div class="sentinel-layout" data-align="baseline" data-wrap>
          ${this.renderInterval(job, "interval_minutes", "Interval")}
          ${this.renderInterval(job, "interval_market_open_minutes", "Market open")}
          ${job.next_run ? b`<span aria-hidden="true">&nbsp;·&nbsp;</span
                ><span>Next ${formatRelativeTime(job.next_run)}</span>` : ""}
        </div>
      </div>
    `;
	}
	renderJobs() {
		const schedules = this.schedules.value?.schedules ?? [];
		return [...new Set(schedules.map((job) => job.category).filter(Boolean))].map((category, index) => b`
        ${index > 0 ? b`<div aria-hidden="true">&nbsp;</div>` : ""}
        <wa-card
          ><span slot="header">${category}</span>
          ${schedules.filter((job) => job.category === category).map((job, jobIndex) => b`
                ${jobIndex > 0 ? b`<wa-divider></wa-divider>` : ""}
                ${this.renderJob(job)}
              `)}
        </wa-card>
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
              <th style="text-align: left">Status</th>
              <th style="text-align: left">Duration</th>
              <th style="text-align: left">Executed</th>
              <th style="text-align: left">Error</th>
            </tr>
          </thead>
          <tbody>
            ${history.map((entry) => b`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${entry.job_id}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    <span data-tone=${statusVariant(entry.status) || ""}
                      >${entry.status}</span
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatDuration(entry.duration_ms)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatDateTime(entry.executed_at, { seconds: true })}
                  </td>
                  <td
                    style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
                  >
                    ${entry.error ?? "-"}
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
		if (error) return b`<span data-tone="error"
        >Error loading scheduler: ${error.message}</span
      >`;
		return b`
      <wa-radio-group
        size="small"
        aria-label="Scheduler view"
        .value=${this.tab}
        @change=${(event) => this.tab = event.currentTarget.value}
      >
        <wa-radio appearance="button" value="status">Status</wa-radio>
        <wa-radio appearance="button" value="jobs">Jobs</wa-radio>
        <wa-radio appearance="button" value="history">History</wa-radio>
      </wa-radio-group>
      <div aria-hidden="true">&nbsp;</div>
      ${this.tab === "jobs" ? this.renderJobs() : this.tab === "history" ? this.renderHistory() : this.renderStatus()}
      ${this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError ? b`<span data-tone="error">${this.actionError}</span>` : ""}
    `;
	}
};
customElements.define("sentinel-scheduler", SentinelScheduler);
// src/sentinel-settings.js
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
		"strategy_deposit_history_months",
		"Deposit History Months",
		12,
		1,
		36,
		1,
		"Months of deposits and withdrawals used to calculate monthly net contributions"
	],
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
			key: "ai_firefox_mcp_base_url",
			label: "Firefox MCP",
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
var SentinelSettings = class extends i$4 {
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
		if (field.type === "toggle") control = b`<wa-switch
        size="small"
        .checked=${Boolean(value)}
        ?disabled=${disabled}
        @change=${(event) => this.updateSetting(field, event.currentTarget.checked)}
        >${field.label}</wa-switch
      >`;
		else if (field.type === "select") control = b`<label
        >${field.label}&nbsp;<wa-select
          size="small"
          .value=${value}
          ?disabled=${disabled}
          @change=${(event) => this.updateSetting(field, event.currentTarget.value)}
        >
          ${field.options.map(([optionValue, label]) => b`
              <wa-option value=${optionValue}>${label}</wa-option>
            `)}
        </wa-select></label
      >`;
		else if (field.type === "model") control = b`
        <label>
          <span>${field.label}</span>
          <input
            .value=${value ?? ""}
            list="sentinel-ai-models"
            style="inline-size: 100%"
            ?disabled=${disabled}
            @change=${(event) => this.updateSetting(field, event.currentTarget.value)}
          />
        </label>
      `;
		else {
			const type = field.type === "password" ? "password" : field.type === "number" ? "number" : "text";
			control = b`<label
        ><span>${field.label}</span>
        <wa-input
          size="small"
          style="inline-size: 100%"
          type=${type}
          .value=${value ?? ""}
          min=${field.min ?? ""}
          max=${field.max ?? ""}
          step=${field.step ?? (field.type === "number" ? 1 : "")}
          ?disabled=${disabled}
          @change=${(event) => strategy ? this.changeStrategy(field, event.currentTarget.value) : this.updateSetting(field, event.currentTarget.value)}
        ></wa-input
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
          <wa-card
            ><span slot="header">${heading}</span>
            <div class="sentinel-layout" data-align="start" data-wrap>
              ${fields.map((field) => b`
                  <div style="flex: 1 1 38ch; min-width: 0">
                    ${this.renderField(field)}
                  </div>
                `)}
            </div>
            ${heading === "Model and research tools" ? b`<div>
                  <wa-button size="small" @click=${() => this.models.refresh()}
                    >Refresh available models</wa-button
                  >
                  ${this.models.error ? b`<span data-tone="error"
                        >${this.models.error.message}</span
                      >` : ""}
                </div>` : ""}
          </wa-card>
        `)}
    `;
	}
	renderPanel() {
		switch (this.tab) {
			case "fees": return this.renderFields(feeFields);
			case "strategy": return b`
          <wa-card
            ><span slot="header">Strategy Tuning</span>
            ${this.renderFields(strategyDraftFields, this.strategyDraft, true)}
            <div aria-hidden="true">&nbsp;</div>
            <wa-button
              size="small"
              ?disabled=${this.busyKey !== ""}
              @click=${this.applyStrategy}
              >Apply Strategy Tuning</wa-button
            >
          </wa-card>
          <div aria-hidden="true">&nbsp;</div>
          ${this.renderFields(strategyFields)}
        `;
			case "forecasting": return this.renderFields(forecastFields);
			case "research": return this.renderResearch();
			case "api": return b`
          ${this.renderFields(apiFields.slice(0, 2))}
          <div aria-hidden="true">&nbsp;</div>
          <wa-card
            ><span slot="header">Freedom24 web login</span>
            <div>
              Used only to fetch PRAAMS portfolio-structure data not exposed by
              the public API.
            </div>
            ${this.renderFields(apiFields.slice(2))}
          </wa-card>
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
		if (this.settings.error) return b`<span data-tone="error"
        >Error loading settings: ${this.settings.error.message}</span
      >`;
		return b`
      <wa-radio-group
        size="small"
        aria-label="Settings section"
        .value=${this.tab}
        @change=${(event) => this.tab = event.currentTarget.value}
      >
        <wa-radio appearance="button" value="trading">Trading</wa-radio>
        <wa-radio appearance="button" value="fees">Fees</wa-radio>
        <wa-radio appearance="button" value="strategy">Strategy</wa-radio>
        <wa-radio appearance="button" value="forecasting">Forecasts</wa-radio>
        <wa-radio appearance="button" value="research">Research</wa-radio>
        <wa-radio appearance="button" value="api">API</wa-radio>
        <wa-radio appearance="button" value="backup">Backup</wa-radio>
      </wa-radio-group>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderPanel()}
      ${this.busyKey ? b`<div aria-live="polite">Saving ${this.busyKey}…</div>` : ""}
      ${this.notice ? b`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError ? b`<span data-tone="error">${this.actionError}</span>` : ""}
    `;
	}
};
customElements.define("sentinel-settings", SentinelSettings);
// src/sentinel-trades.js
var SentinelTrades = class extends i$4 {
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
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <label
          >Symbol&nbsp;<wa-select
            size="small"
            .value=${this.symbol}
            @change=${(event) => this.changeFilter("symbol", event.currentTarget.value)}
          >
            <wa-option value="">All symbols</wa-option>
            ${symbols.map((symbol) => b`<wa-option value=${symbol}>${symbol}</wa-option>`)}
          </wa-select></label
        >

        <label
          >Side&nbsp;<wa-select
            size="small"
            .value=${this.side}
            @change=${(event) => this.changeFilter("side", event.currentTarget.value)}
          >
            <wa-option value="">All</wa-option>
            <wa-option value="BUY">Buy</wa-option>
            <wa-option value="SELL">Sell</wa-option>
          </wa-select></label
        >

        <label
          >From&nbsp;<wa-input
            size="small"
            type="date"
            .value=${this.startDate}
            @change=${(event) => this.changeFilter("startDate", event.currentTarget.value)}
          ></wa-input
        ></label>

        <label
          >To&nbsp;<wa-input
            size="small"
            type="date"
            .value=${this.endDate}
            @change=${(event) => this.changeFilter("endDate", event.currentTarget.value)}
          ></wa-input
        ></label>

        <wa-button
          size="small"
          ?disabled=${this.syncing}
          @click=${this.syncTrades}
          >${this.syncing ? "Syncing…" : "Sync from Broker"}</wa-button
        >
      </div>
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
              <th style="text-align: left">Symbol</th>
              <th style="text-align: left">Side</th>
              <th style="text-align: left">Qty</th>
              <th style="text-align: left">Price</th>
              <th style="text-align: left">Value</th>
              <th style="text-align: left">Commission</th>
              <th style="text-align: left">Currency</th>
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
                    ${trade.symbol}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    <span
                      data-tone=${trade.side === "BUY" ? "success" : "error"}
                      >${trade.side}</span
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(quantity, 0)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(price, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(value, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(commission, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${currency}
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
        <wa-button
          size="small"
          ?disabled=${this.page <= 1}
          @click=${() => this.changePage(this.page - 1)}
          >Previous</wa-button
        >
        Page ${this.page} / ${pages}
        <wa-button
          size="small"
          ?disabled=${this.page >= pages}
          @click=${() => this.changePage(this.page + 1)}
          >Next</wa-button
        >
      </div>
    `;
	}
	render() {
		if (this.securities.loading && !this.securities.value) return b`<div>Loading trade filters…</div>`;
		return b`
      ${this.renderControls()}
      <div aria-hidden="true">&nbsp;</div>
      ${this.trades.loading && !this.trades.value ? b`<div>Loading trades…</div>` : this.trades.error ? b`<span data-tone="error"
              >Error loading trades: ${this.trades.error.message}</span
            >` : this.renderTable()}
      ${this.renderPagination()}
      ${this.actionError ? b`<span data-tone="error">${this.actionError}</span>` : ""}
    `;
	}
};
customElements.define("sentinel-trades", SentinelTrades);
// src/sentinel-header.js
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
var SentinelHeader = class extends i$4 {
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
	async requestModalClose(event) {
		if (event.target !== event.currentTarget) return;
		const dialog = event.currentTarget;
		if (this.confirmedClose === dialog) {
			this.confirmedClose = void 0;
			return;
		}
		const tasks = dialog.querySelector("sentinel-tasks");
		if (!tasks?.dirty) return;
		event.preventDefault();
		if (this.confirmingClose) return;
		this.confirmingClose = true;
		try {
			if (await tasks.confirmClose() && dialog.isConnected) {
				this.confirmedClose = dialog;
				dialog.open = false;
			}
		} finally {
			this.confirmingClose = false;
		}
	}
	get visibleActions() {
		const live = this.health.value?.trading_mode === "live";
		return actions.filter((action) => !action.researchOnly || !live);
	}
	renderAction(action) {
		return b`
      <wa-button
        size="xs"
        appearance="plain"
        variant="neutral"
        aria-controls=${`sentinel-${action.id}-modal`}
        aria-expanded=${this.activeModal === action.id ? "true" : "false"}
        @click=${() => this.openModal(action.id)}
        >${action.label}</wa-button
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
      <wa-dialog
        id=${`sentinel-${action.id}-modal`}
        label=${action.heading}
        open
        @wa-hide=${this.requestModalClose}
        @wa-after-hide=${(event) => {
			if (event.target === event.currentTarget) this.closeModal(action.id);
		}}
        >${this.renderModalContent(action.id)}</wa-dialog
      >
    `;
	}
	render() {
		return b`
      <header>
        <div class="sentinel-toolbar">
          <nav aria-label="Application">
            <div
              class="sentinel-layout sentinel-app-nav"
              data-align="center"
              data-wrap
            >
              ${this.visibleActions.map((action) => this.renderAction(action))}
            </div>
          </nav>
        </div>
        ${this.renderModal()}
      </header>
    `;
	}
};
customElements.define("sentinel-header", SentinelHeader);
// src/sentinel-planner-status.js
var rowStyle = `
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.25rem 1rem;
`;
var labelStyle = "flex: 0 0 6.5rem; font-weight: 600";
var listStyle = `
  display: flex; flex: 1 1 21rem; flex-wrap: wrap; align-items: baseline;
  gap: 0.375rem 1rem; min-inline-size: 0; margin: 0; padding: 0; list-style: none;
`;
var planHeading = b`
  <h2
    id="sentinel-plan-title"
    style="${labelStyle}; font-size: 1rem; line-height: 1.25; margin: 0"
  >
    Plan
  </h2>
`;
var SentinelPlannerStatus = class extends i$4 {
	planner = new LiveResource(this, (signal) => getJson("/api/planner/recommendations", { signal }), { interval: 6e4 });
	createRenderRoot() {
		return this;
	}
	refreshForCashSetting = (event) => {
		if (event.detail?.key === "simulated_cash_eur" || event.detail?.key === "trading_mode") this.planner.refresh();
	};
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-setting-changed", this.refreshForCashSetting);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-setting-changed", this.refreshForCashSetting);
		super.disconnectedCallback();
	}
	renderRecommendation(recommendation) {
		const isSell = recommendation.action === "sell";
		const waitingForMarket = recommendation.market_open === false;
		const percentage = isSell && recommendation.current_value_eur > 0 ? `${Math.round(Math.abs(recommendation.value_delta_eur) / recommendation.current_value_eur * 100)}%` : "";
		const variant = waitingForMarket ? "neutral" : isSell ? "danger" : "success";
		return b`
      <li
        title=${[waitingForMarket ? "Waiting for market to open" : "", recommendation.reason ?? ""].filter(Boolean).join(" · ")}
        style="
          display: inline-flex; flex-wrap: wrap; align-items: center;
          gap: 0.15rem 0.35rem; min-inline-size: 0;
        "
      >
        <wa-badge variant=${variant} appearance="filled"
          >${isSell ? "Sell" : "Buy"}</wa-badge
        >
        <strong style="font-weight: 650">${recommendation.symbol}</strong>
        <span>${formatCurrency(Math.abs(recommendation.value_delta_eur))}</span>
        ${percentage ? b`<span style="color: var(--wa-color-text-quiet)"
              >(${percentage})</span
            >` : ""}
        ${waitingForMarket ? b`<span
              style="color: var(--wa-color-text-quiet); font-size: 0.75rem"
              >Market closed</span
            >` : ""}
      </li>
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
		return targets.filter((target) => Math.abs(Number(target.gap_eur ?? 0)) > .005).sort((left, right) => Math.abs(Number(right.gap_eur)) - Math.abs(Number(left.gap_eur)));
	}
	renderTarget(target) {
		const gap = Number(target.gap_eur ?? 0);
		const quantityDelta = Number(target.quantity_delta ?? 0);
		const quantity = !target.isCash && Math.abs(quantityDelta) > 1e-4 ? `${quantityDelta > 0 ? "+" : "-"}${Math.abs(quantityDelta).toLocaleString()} sh` : "";
		return b`
      <li class="plan-target" title=${target.isCash ? "Cash left after deploying all affordable whole-lot purchases" : `AI research ${target.ai_research_multiplier == null ? "-" : Number(target.ai_research_multiplier).toFixed(2)}, opportunity ${Number(target.opportunity_score ?? 0).toFixed(2)}`}>
        <strong style="font-weight: 600">${target.symbol}</strong>
        <span title="Target value"
          >${formatCurrency(target.target_value_eur)}</span
        >
        <span class="plan-target-gap" title="Gap to target"
          >${gap >= 0 ? "+" : "-"}${formatCurrency(Math.abs(gap))}</span
        >
        <span class="plan-target-quantity" title="Share change"
          >${quantity}</span
        >
      </li>
    `;
	}
	renderPlanner(planner) {
		const recommendations = planner.recommendations ?? [];
		const plan = planner.plan;
		const summary = planner.summary;
		const targets = this.targetItems(plan);
		const gapLabel = `${plan?.horizon_months ?? 12} mo gaps`;
		return b`
      <div style=${rowStyle}>
        ${planHeading}
        <ul
          class="plan-inline-list"
          role="list"
          aria-label="Current plan"
          style=${listStyle}
        >
          ${recommendations.length > 0 ? recommendations.map((recommendation) => this.renderRecommendation(recommendation)) : b`<li style="color: var(--wa-color-text-quiet)">
                No pending actions
              </li>`}
        </ul>
      </div>
      ${plan ? b`
            <div style="${rowStyle} color: var(--wa-color-text-quiet)">
              <span id="sentinel-plan-projection-label" style=${labelStyle}
                >Projection</span
              >
              <ul
                class="plan-inline-list"
                role="list"
                aria-labelledby="sentinel-plan-projection-label"
                style=${listStyle}
              >
                <li>
                  <strong
                    style="color: var(--wa-color-text-normal); font-weight: 650"
                    >${formatCurrency(plan.terminal_portfolio_value_eur)}</strong
                  >
                  by
                  <time datetime=${plan.horizon_end_date}
                    >${plan.horizon_end_date}</time
                  >
                </li>
                <li>${formatCurrency(plan.avg_monthly_net_deposit_eur)}/mo</li>
                <li>${(plan.targets ?? []).length} securities</li>
                ${summary ? b`<li>
                      Cash after trades
                      ${formatCurrency(summary.cash_after_plan)}
                    </li>` : ""}
              </ul>
            </div>
          ` : ""}
      <div>
        <div class="plan-targets-header">
          <span id="sentinel-plan-gap-label" style="font-weight: 600"
            >${gapLabel}</span
          >
          ${targets.length > 0 ? b`<span class="plan-target-gap"
                >Target value · Gap · Shares</span
              >` : ""}
        </div>
        <ul
          role="list"
          aria-labelledby="sentinel-plan-gap-label"
          class="plan-targets"
        >
          ${targets.length > 0 ? targets.map((target) => this.renderTarget(target)) : b`<li>Target unavailable</li>`}
        </ul>
      </div>
    `;
	}
	render() {
		const loading = this.planner.loading && !this.planner.value;
		const error = this.planner.error;
		return b`
      <wa-card appearance="outlined">
        <section
          aria-labelledby="sentinel-plan-title"
          style="
          display: grid;
          gap: 0.45rem;
          overflow-wrap: anywhere;
        "
        >
          ${loading || error ? b`
                <div style=${rowStyle}>
                  ${planHeading}
                  <span
                    role="status"
                    style="color: ${error ? "var(--wa-color-danger-on-normal)" : "var(--wa-color-text-quiet)"}"
                  >
                    ${error ? "Plan unavailable" : "Loading plan…"}
                  </span>
                </div>
              ` : this.renderPlanner(this.planner.value)}
        </section>
      </wa-card>
    `;
	}
};
customElements.define("sentinel-planner-status", SentinelPlannerStatus);
// src/sentinel-portfolio-pnl.js
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
var SentinelPortfolioPnl = class extends i$4 {
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
		return variant ? b`<span data-tone=${variant}>${formatted}</span>` : b`<span>${formatted}</span>`;
	}
	renderSummary(summary, sinceInceptionMoneyWeightedReturn) {
		return b`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span title="Annual investor-return target" style="white-space: nowrap"
          >Target
          p.a.&nbsp;${this.renderValue(summary.target_ann_return, formatPercent(summary.target_ann_return, 1))}</span
        >
        <div class="sentinel-layout" data-align="baseline" data-wrap>
          <span
            title="Money-weighted annual return using the date and amount of every deposit and withdrawal"
            style="white-space: nowrap"
            >Overall yearly
            return&nbsp;${this.renderValue(sinceInceptionMoneyWeightedReturn, formatPercent(sinceInceptionMoneyWeightedReturn, 1))}</span
          >
          <span
            title="Money-weighted annual return over the last 365 days, using the opening value and every deposit and withdrawal"
            style="white-space: nowrap"
            >&nbsp;·&nbsp;Last 365
            days&nbsp;${this.renderValue(summary.trailing_365d_money_weighted_return_pct, formatPercent(summary.trailing_365d_money_weighted_return_pct, 1))}</span
          >
        </div>
      </div>
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
      <div class="sentinel-layout" data-align="center" data-wrap>
        <span>Range&nbsp;</span>
        <wa-radio-group
          size="xs"
          orientation="horizontal"
          aria-label="P/L chart period"
          .value=${this.pnlPeriod}
          @change=${this.changePeriod}
        >
          <wa-radio appearance="button" value="3M">3M</wa-radio>
          <wa-radio appearance="button" value="6M">6M</wa-radio>
          <wa-radio appearance="button" value="1Y">1Y</wa-radio>
          <wa-radio appearance="button" value="ALL">ALL</wa-radio>
        </wa-radio-group>
      </div>
    `;
	}
	renderChartRow(label, values, latest, minimum, maximum, threshold) {
		const comparison = Number.isFinite(latest) && Number.isFinite(threshold) ? latest - threshold : void 0;
		return b`
      <div class="sentinel-layout" data-align="start">
        <span
          data-chart-space
          style="display: block; flex: 1 1 0; min-width: 0; white-space: nowrap"
          >${b`<sentinel-chart
      role="img"
      aria-label="${label} annualized return trend"
      height="4"
      min=${minimum}
      max=${maximum}
      threshold=${threshold ?? ""}
      .values=${values}
    ></sentinel-chart>`}</span
        >
        <span style="white-space: nowrap"
          >&nbsp;${Number.isFinite(comparison) ? this.renderValue(comparison, formatPercent(latest, 1)) : formatPercent(latest, 1)}</span
        >
      </div>
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
		else if (this.performance.error) content = b`<span data-tone="error"
        >Portfolio P&amp;L unavailable</span
      >`;
		else if (!this.performance.value?.periodStats || !this.performance.value?.summary) content = b`<span>Not enough data yet</span>`;
		else content = b`
        ${this.renderSummary(this.performance.value.summary, this.performance.value.sinceInceptionMoneyWeightedReturn)}
        ${this.renderControls()}
        ${this.renderChart(this.performance.value.snapshots, this.performance.value.summary)}
        ${this.renderTable(this.performance.value.periodStats)}
      `;
		return b`<wa-card
      ><span slot="header">Portfolio P&amp;L</span>${content}</wa-card
    >`;
	}
};
customElements.define("sentinel-portfolio-pnl", SentinelPortfolioPnl);
// src/sentinel-portfolio-status.js
var SentinelPortfolioStatus = class extends i$4 {
	static properties = {
		cashDraft: { state: true },
		cashError: { state: true },
		cashPending: { state: true },
		editingCash: { state: true }
	};
	constructor() {
		super();
		this.cashDraft = "";
		this.cashError = "";
		this.cashPending = false;
		this.editingCash = false;
	}
	portfolio = new LiveResource(this, (signal) => getJson("/api/portfolio", { signal }), { interval: 6e4 });
	cashFlows = new LiveResource(this, (signal) => getJson("/api/cashflows", { signal }), { interval: 3e5 });
	settings = new LiveResource(this, (signal) => getJson("/api/settings", { signal }), { interval: 0 });
	refreshForSetting = (event) => {
		if (event.detail?.source !== this && (event.detail?.key === "simulated_cash_eur" || event.detail?.key === "trading_mode")) {
			this.settings.refresh();
			this.portfolio.refresh();
		}
	};
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-setting-changed", this.refreshForSetting);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-setting-changed", this.refreshForSetting);
		super.disconnectedCallback();
	}
	createRenderRoot() {
		return this;
	}
	renderCashBreakdown(cash) {
		const balances = Object.entries(cash ?? {}).filter(([, amount]) => amount !== 0);
		if (balances.length === 0) return "";
		return b`&nbsp;(${balances.map(([currency, amount], index) => b`${index > 0 ? ", " : ""}${currency}&nbsp;${formatCurrency(amount, currency)}`)})`;
	}
	get isResearchMode() {
		return this.settings.value?.trading_mode === "research";
	}
	get simulatedCash() {
		return this.settings.value?.simulated_cash_eur;
	}
	get cashIsSimulated() {
		return this.isResearchMode && this.simulatedCash !== null && this.simulatedCash !== void 0;
	}
	startCashEdit() {
		this.cashDraft = String(this.cashIsSimulated ? this.simulatedCash : this.portfolio.value?.total_cash_eur ?? 0);
		this.cashError = "";
		this.editingCash = true;
		this.updateComplete.then(() => this.querySelector("wa-input[aria-label=\"Simulated cash in EUR\"]")?.select());
	}
	cancelCashEdit() {
		this.cashDraft = "";
		this.cashError = "";
		this.editingCash = false;
	}
	async setCashOverride(value) {
		this.cashPending = true;
		this.cashError = "";
		try {
			await putJson("/api/settings/simulated_cash_eur", { value });
			this.settings.value = {
				...this.settings.value,
				simulated_cash_eur: value
			};
			this.cancelCashEdit();
			await this.portfolio.refresh();
			window.dispatchEvent(new CustomEvent("sentinel-setting-changed", { detail: {
				key: "simulated_cash_eur",
				value,
				source: this
			} }));
		} catch (error) {
			this.cashError = error.message;
		} finally {
			this.cashPending = false;
		}
	}
	async saveCash(event) {
		event.preventDefault();
		const draft = this.cashDraft.trim();
		const value = draft === "" ? null : Number(draft);
		if (value !== null && !Number.isFinite(value)) {
			this.cashError = "Cash must be a finite number.";
			return;
		}
		await this.setCashOverride(value);
	}
	renderCash(portfolio) {
		if (this.editingCash && this.isResearchMode) return b`
        <form
          class="sentinel-layout"
          data-align="center"
          data-wrap
          @submit=${this.saveCash}
        >
          <label class="sentinel-layout" data-align="center">
            <span>Cash</span>
            <wa-input
              size="small"
              aria-label="Simulated cash in EUR"
              type="number"
              step="any"
              style="inline-size: 12ch; max-inline-size: 100%"
              .value=${this.cashDraft}
              ?disabled=${this.cashPending}
              @input=${(event) => this.cashDraft = event.currentTarget.value}
              @keydown=${(event) => {
			if (event.key === "Escape") this.cancelCashEdit();
		}}
            ></wa-input>
          </label>
          <wa-button size="small" type="submit" ?disabled=${this.cashPending}
            >${this.cashPending ? "Saving…" : "Apply"}</wa-button
          >
          <wa-button
            size="small"
            type="button"
            ?disabled=${this.cashPending}
            @click=${this.cancelCashEdit}
            >Cancel</wa-button
          >
        </form>
      `;
		return b`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <span
          >Cash&nbsp;<strong>${formatCurrency(portfolio.total_cash_eur)}</strong>${this.cashIsSimulated ? "" : this.renderCashBreakdown(portfolio.cash)}</span
        >
        ${this.cashIsSimulated ? b`<span data-tone="warning">[simulated]</span>` : ""}
        ${this.isResearchMode ? b`
              <wa-button
                size="xs"
                appearance="plain"
                aria-label="Edit simulated cash"
                title="Change the cash used by research-mode planning"
                ?disabled=${this.cashPending}
                @click=${this.startCashEdit}
                >Edit</wa-button
              >
              ${this.cashIsSimulated ? b`<wa-button
                    size="xs"
                    appearance="plain"
                    aria-label="Use real cash"
                    title="Clear the simulated cash override"
                    ?disabled=${this.cashPending}
                    @click=${() => this.setCashOverride(null)}
                    >Use real</wa-button
                  >` : ""}
            ` : ""}
      </div>
      ${this.cashError ? b`<span data-tone="error">${this.cashError}</span>` : ""}
    `;
	}
	renderPortfolio() {
		const portfolio = this.portfolio.value;
		const totalProfit = Number(this.cashFlows.value?.total_profit);
		return b`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <span
          >Value&nbsp;<strong
            ><span data-tone=${totalProfit > 0 ? "success" : totalProfit < 0 ? "error" : void 0}
              >${formatCurrency(portfolio.total_value_eur)}</span
            ></strong
          ></span
        >

        ${this.renderCash(portfolio)}
      </div>
    `;
	}
	renderCashFlows() {
		const cashFlows = this.cashFlows.value;
		if (!cashFlows) return "";
		const totalFees = cashFlows.fees + cashFlows.taxes;
		return b`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <span
          >Deposits&nbsp;<strong
            >${formatCurrency(cashFlows.deposits)}</strong
          ></span
        >

        <span
          >Withdrawals&nbsp;<strong
            >${formatCurrency(cashFlows.withdrawals)}</strong
          ></span
        >

        <span
          >Dividends&nbsp;<strong
            >${formatCurrency(cashFlows.dividends)}</strong
          ></span
        >

        <span>Fees&nbsp;<strong>${formatCurrency(totalFees)}</strong></span>
        <span aria-hidden="true">&nbsp;&nbsp;—&nbsp;&nbsp;</span>
        <span
          >Total Profit&nbsp;<strong
            ><span data-tone="warning"
              >${formatCurrency(cashFlows.total_profit)}</span
            ></strong
          ></span
        >
      </div>
    `;
	}
	render() {
		let content;
		if (this.portfolio.loading && !this.portfolio.value) content = b`<span>Loading portfolio…</span>`;
		else if (this.portfolio.error) content = b`<span data-tone="error">Portfolio unavailable</span>`;
		else content = this.renderPortfolio();
		return b`<section aria-label="Portfolio status">
      ${content}${this.renderCashFlows()}
    </section>`;
	}
};
customElements.define("sentinel-portfolio-status", SentinelPortfolioStatus);
var FIRE_WITHDRAWAL_RATE = .04;
var AVG_DAYS_PER_MONTH = 365.25 / 12;
var MILLISECONDS_PER_DAY = 864e5;
function calculateProjectedMonthlyIncome(projectedValueEur, expectedInflationPct, monthsAhead) {
	const value = Number(projectedValueEur);
	const inflationPct = Number(expectedInflationPct);
	const months = Number(monthsAhead);
	if (!Number.isFinite(value) || value < 0 || !Number.isFinite(inflationPct) || inflationPct <= -100 || !Number.isFinite(months) || months < 0) return;
	const monthlyIncomeEur = value * FIRE_WITHDRAWAL_RATE / 12;
	return {
		monthlyIncomeEur,
		monthlyIncomeTodayEur: monthlyIncomeEur / (1 + inflationPct / 100) ** (months / 12)
	};
}
function fireYearsRemaining(monthsAhead) {
	const months = Number(monthsAhead);
	if (!Number.isFinite(months) || months < 0) return;
	return Math.ceil(months / 12);
}
function formatFireProjection(plan) {
	const achievement = plan?.achievement;
	if (!achievement) return "Not reached under current assumptions";
	if (achievement.months_ahead === 0) return "Funded now";
	const yearsRemaining = plan.yearsRemaining;
	const unit = yearsRemaining === 1 ? "year" : "years";
	return `${String(achievement.date).slice(0, 4)} (${yearsRemaining} ${unit} remaining)`;
}
function projectedDate(currentDate, monthsAhead) {
	const start = Date.parse(`${currentDate}T00:00:00Z`);
	if (!Number.isFinite(start)) return;
	const date = new Date(start + Math.round(monthsAhead * AVG_DAYS_PER_MONTH) * MILLISECONDS_PER_DAY);
	return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : void 0;
}
function fireValuesAtMonth(monthlyExpensesEur, annualInflation, monthsAhead) {
	const monthlyExpenses = monthlyExpensesEur * (1 + annualInflation) ** (monthsAhead / 12);
	const annualExpenses = monthlyExpenses * 12;
	return {
		monthly_expenses_eur: monthlyExpenses,
		annual_expenses_eur: annualExpenses,
		target_eur: annualExpenses * 25
	};
}
function findAchievement(monthlyExpensesEur, annualInflation, projection, summary) {
	for (const point of projection) {
		const monthsAhead = Number(point.months_ahead);
		const projectedValue = Number(point.projected_value_eur);
		const fireValues = fireValuesAtMonth(monthlyExpensesEur, annualInflation, monthsAhead);
		if (projectedValue >= fireValues.target_eur) return {
			...point,
			...fireValues,
			extended: false
		};
	}
	const monthlyReturn = Number(summary?.monthly_return_rate ?? 0);
	const monthlyDeposit = Number(summary?.avg_monthly_net_deposit_eur);
	const currentDate = summary?.current_date;
	const projectionMonths = Number(summary?.projection_months ?? 0);
	let value = Number(summary?.current_value_eur);
	let month = 0;
	let fireValues = fireValuesAtMonth(monthlyExpensesEur, annualInflation, month);
	let previousFundingRatio = value / fireValues.target_eur;
	const portfolioGrowthFactor = 1 + monthlyReturn;
	const monthlyInflationFactor = (1 + annualInflation) ** (1 / 12);
	if (!Number.isFinite(value) || !Number.isSafeInteger(month) || !Number.isFinite(monthlyReturn) || monthlyReturn <= -1 || !Number.isFinite(monthlyDeposit) || !currentDate || !Number.isFinite(previousFundingRatio)) return;
	while (Number.isSafeInteger(month)) {
		month += 1;
		value = Math.max(0, value * portfolioGrowthFactor + monthlyDeposit);
		fireValues = fireValuesAtMonth(monthlyExpensesEur, annualInflation, month);
		if (!Number.isFinite(fireValues.target_eur)) return;
		if (value >= fireValues.target_eur) {
			const date = projectedDate(currentDate, month);
			return date ? {
				date,
				projected_value_eur: value,
				months_ahead: month,
				extended: month > projectionMonths,
				...fireValues
			} : void 0;
		}
		if (!Number.isFinite(value) || value === 0 && monthlyDeposit <= 0) return;
		const fundingRatio = value / fireValues.target_eur;
		if (monthlyInflationFactor >= 1 && portfolioGrowthFactor <= monthlyInflationFactor && fundingRatio <= previousFundingRatio) return;
		previousFundingRatio = fundingRatio;
	}
}
function calculateFirePlan(monthlyExpensesEur, expectedInflationPct, projection, summary) {
	const monthlyExpenses = Number(monthlyExpensesEur);
	const inflationPct = Number(expectedInflationPct);
	if (!Number.isFinite(monthlyExpenses) || monthlyExpenses <= 0 || !Number.isFinite(inflationPct) || inflationPct <= -100) return;
	const annualInflation = inflationPct / 100;
	const annualExpensesEur = monthlyExpenses * 12;
	const currentTargetEur = annualExpensesEur * 25;
	if (!Number.isFinite(annualExpensesEur) || !Number.isFinite(currentTargetEur)) return;
	const achievement = findAchievement(monthlyExpenses, annualInflation, projection, summary);
	const retirementTargetEur = achievement?.target_eur;
	const annualWithdrawalEur = retirementTargetEur ? retirementTargetEur * FIRE_WITHDRAWAL_RATE : void 0;
	return {
		monthlyExpensesEur: monthlyExpenses,
		annualExpensesEur,
		expectedInflationPct: inflationPct,
		currentTargetEur,
		retirementMonthlyExpensesEur: achievement?.monthly_expenses_eur,
		retirementAnnualExpensesEur: achievement?.annual_expenses_eur,
		retirementTargetEur,
		annualWithdrawalEur,
		monthlyWithdrawalEur: annualWithdrawalEur ? annualWithdrawalEur / 12 : void 0,
		yearsRemaining: achievement ? fireYearsRemaining(achievement.months_ahead) : void 0,
		achievement
	};
}
// src/sentinel-portfolio-value.js
var CHECKPOINT_COUNT = 25;
var DEPOSIT_HISTORY_MONTHS_KEY = "strategy_deposit_history_months";
function formatSignedCurrency(value, currency = "EUR", fractionDigits = 0) {
	if (value === null || value === void 0) return "-";
	return `${value > 0 ? "+" : ""}${formatCurrency(value, currency, fractionDigits)}`;
}
function checkpointDates(currentDate) {
	const current = /* @__PURE__ */ new Date(`${currentDate}T00:00:00Z`);
	if (Number.isNaN(current.getTime())) return [];
	const firstYear = current.getUTCFullYear() + 1;
	const month = current.getUTCMonth();
	const day = current.getUTCDate();
	return Array.from({ length: CHECKPOINT_COUNT }, (_, index) => {
		const year = firstYear + index;
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
var SentinelPortfolioValue = class extends i$4 {
	static properties = {
		editingNetDeposit: { state: true },
		expectedInflationDraft: { state: true },
		fireAssumptionsError: { state: true },
		monthlyExpensesDraft: { state: true },
		netDepositDraft: { state: true },
		netDepositOverride: { state: true },
		savingFireAssumptions: { state: true }
	};
	constructor() {
		super();
		this.editingNetDeposit = false;
		this.expectedInflationDraft = null;
		this.fireAssumptionsError = "";
		this.monthlyExpensesDraft = null;
		this.netDepositDraft = "";
		this.netDepositOverride = null;
		this.savingFireAssumptions = false;
	}
	projection = new LiveResource(this, async (signal) => {
		const params = new URLSearchParams({ years: "25" });
		if (this.netDepositOverride !== null) params.set("avg_monthly_net_deposit_eur", String(this.netDepositOverride));
		const [projection, settings] = await Promise.all([getJson(`/api/portfolio/value-projection?${params}`, { signal }), getJson("/api/settings", { signal })]);
		return {
			...projection,
			expectedInflationPct: settings.fire_expected_inflation_pct,
			monthlyExpensesEur: settings.fire_monthly_expenses_eur
		};
	}, { interval: 3e5 });
	refreshForSetting = (event) => {
		if (event.detail?.key === DEPOSIT_HISTORY_MONTHS_KEY) this.projection.refresh();
	};
	connectedCallback() {
		super.connectedCallback();
		window.addEventListener("sentinel-setting-changed", this.refreshForSetting);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-setting-changed", this.refreshForSetting);
		super.disconnectedCallback();
	}
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
				projectedNetDeposits: data.summary.current_net_deposits_eur + data.summary.avg_monthly_net_deposit_eur * point.months_ahead,
				income: calculateProjectedMonthlyIncome(point.projected_value_eur, data.expectedInflationPct, point.months_ahead)
			};
		}).filter(Boolean);
	}
	startNetDepositEdit(summary) {
		this.netDepositDraft = String(summary.avg_monthly_net_deposit_eur);
		this.editingNetDeposit = true;
		this.updateComplete.then(() => this.querySelector("wa-input[aria-label=\"Monthly net deposit assumption\"]")?.select());
	}
	cancelNetDepositEdit() {
		this.editingNetDeposit = false;
		this.netDepositDraft = "";
	}
	applyNetDepositOverride(event) {
		event.preventDefault();
		const value = Number(this.netDepositDraft);
		if (!Number.isFinite(value)) return;
		this.netDepositOverride = value;
		this.cancelNetDepositEdit();
		this.projection.refresh();
	}
	resetNetDepositOverride() {
		this.netDepositOverride = null;
		this.cancelNetDepositEdit();
		this.projection.refresh();
	}
	async saveFireAssumptions(event) {
		event.preventDefault();
		if (this.savingFireAssumptions) return;
		const values = {};
		if (this.monthlyExpensesDraft !== null) {
			const expenses = Number(this.monthlyExpensesDraft);
			if (!Number.isFinite(expenses) || expenses <= 0) {
				this.fireAssumptionsError = "Monthly retirement expenses must be greater than zero.";
				return;
			}
			values.fire_monthly_expenses_eur = expenses;
		}
		if (this.expectedInflationDraft !== null) {
			const inflation = Number(this.expectedInflationDraft);
			if (this.expectedInflationDraft === "" || !Number.isFinite(inflation) || inflation <= -100) {
				this.fireAssumptionsError = "Expected annual inflation must be greater than -100%.";
				return;
			}
			values.fire_expected_inflation_pct = inflation;
		}
		const entries = Object.entries(values);
		if (entries.length === 0) return;
		this.savingFireAssumptions = true;
		this.fireAssumptionsError = "";
		try {
			if (entries.length === 1) {
				const [[key, value]] = entries;
				await putJson(`/api/settings/${key}`, { value });
			} else await putJson("/api/settings", { values });
			this.monthlyExpensesDraft = null;
			this.expectedInflationDraft = null;
			await this.projection.refresh();
		} catch (error) {
			this.fireAssumptionsError = error.message;
		} finally {
			this.savingFireAssumptions = false;
		}
	}
	renderFireCalculator(data) {
		const fire = calculateFirePlan(data.monthlyExpensesEur, data.expectedInflationPct, data.projection, data.summary);
		return b`
      ${fire ? b`
            <dl class="fire-outcomes">
              <div>
                <dt>Projected FIRE</dt>
                <dd data-tone=${fire.achievement ? "success" : void 0}>
                  ${formatFireProjection(fire)}
                </dd>
              </div>
              <div>
                <dt>F.U. Money today</dt>
                <dd>${formatCurrency(fire.currentTargetEur, "EUR", 0)}</dd>
              </div>
            </dl>
          ` : b`<p>Enter monthly household expenses to calculate FIRE.</p>`}
      ${fire ? b`
            ${fire.achievement ? b`
                  <div>
                    At ${fire.expectedInflationPct.toFixed(2)}% expected annual
                    inflation,
                    ${formatCurrency(fire.monthlyExpensesEur, "EUR", 0)}/month
                    today is estimated to cost
                    ${formatCurrency(fire.retirementMonthlyExpensesEur, "EUR", 0)}/month
                    in ${String(fire.achievement.date).slice(0, 4)}.
                  </div>
                  <div>
                    F.U. Money required then:
                    ${formatCurrency(fire.retirementTargetEur, "EUR", 0)}. Its
                    initial 4% annual withdrawal is
                    ${formatCurrency(fire.annualWithdrawalEur, "EUR", 0)}/year,
                    or
                    ${formatCurrency(fire.monthlyWithdrawalEur, "EUR", 0)}/month.
                  </div>
                ` : b`<div>
                  The portfolio does not catch the inflation-adjusted F.U. Money
                  target under the current assumptions.
                </div>`}
            <div>
              The estimate assumes the portfolio's actual Historical MWR,
              current Net/mo, and expected inflation continue. After retirement,
              withdrawals must keep rising with inflation to preserve today's
              purchasing power.
            </div>
          ` : ""}
    `;
	}
	renderFireAssumptions(data) {
		return b`
      <form class="fire-assumptions" @submit=${this.saveFireAssumptions}>
        <label
          class="fire-assumption-field"
          title="Monthly retirement expenses in today's prices"
        >
          <span>Monthly expenses</span>
          <wa-input
            id="fire-monthly-expenses"
            size="xs"
            aria-label="Monthly retirement expenses in today's prices in EUR"
            type="number"
            min="0.01"
            step="0.01"
            .value=${this.monthlyExpensesDraft ?? data.monthlyExpensesEur ?? ""}
            ?disabled=${this.savingFireAssumptions}
            @input=${(event) => this.monthlyExpensesDraft = event.currentTarget.value}
            ><span slot="start" aria-hidden="true">€</span></wa-input
          >
        </label>
        <label class="fire-assumption-field">
          <span>Annual inflation</span>
          <wa-input
            id="fire-inflation"
            size="xs"
            aria-label="Expected annual inflation percentage"
            type="number"
            min="-99.99"
            step="0.01"
            .value=${this.expectedInflationDraft ?? data.expectedInflationPct}
            ?disabled=${this.savingFireAssumptions}
            @input=${(event) => this.expectedInflationDraft = event.currentTarget.value}
            ><span slot="end" aria-hidden="true">%</span></wa-input
          >
        </label>
        <wa-button
          size="xs"
          appearance="outlined"
          type="submit"
          ?disabled=${this.savingFireAssumptions || this.monthlyExpensesDraft === null && this.expectedInflationDraft === null}
          >${this.savingFireAssumptions ? "Saving…" : "Save"}</wa-button
        >
      </form>
    `;
	}
	renderNetDeposit(summary) {
		if (this.editingNetDeposit) return b`
        <form style="display: inline" @submit=${this.applyNetDepositOverride}>
          <span>
            Net/mo&nbsp;<wa-input
              size="small"
              aria-label="Monthly net deposit assumption"
              type="number"
              step="0.01"
              style="inline-size: 7rem"
              .value=${this.netDepositDraft}
              @input=${(event) => this.netDepositDraft = event.currentTarget.value}
              @keydown=${(event) => {
			if (event.key === "Escape") this.cancelNetDepositEdit();
		}}
            ></wa-input
            >&nbsp;<wa-button size="small" type="submit">Apply</wa-button
            >&nbsp;<wa-button size="small" @click=${this.cancelNetDepositEdit}
              >Cancel</wa-button
            ></span
          >
        </form>
      `;
		const overridden = this.netDepositOverride !== null;
		return b`
      <span>
        ${summary.deposit_window_months}M net/mo&nbsp;<wa-button
          size="xs"
          appearance="plain"
          aria-label="Edit monthly net deposit assumption"
          @click=${() => this.startNetDepositEdit(summary)}
          >${formatCurrency(summary.avg_monthly_net_deposit_eur, "EUR", 0)}</wa-button
        >${overridden ? b`&nbsp;actual&nbsp;${formatCurrency(summary.actual_avg_monthly_net_deposit_eur, "EUR", 0)}&nbsp;<wa-button
                size="xs"
                appearance="plain"
                aria-label="Reset monthly net deposit assumption to actual"
                @click=${this.resetNetDepositOverride}
                >Reset</wa-button
              >` : ""}</span
      >
    `;
	}
	renderMetrics(summary, startYear, endYear) {
		const pnlVariant = summary.total_pnl_pct >= 0 ? "success" : "error";
		const runRateVariant = Number.isFinite(summary.annualized_total_pnl_pct) ? summary.annualized_total_pnl_pct >= 0 ? "success" : "error" : void 0;
		return b`
      <div
        class="sentinel-layout fire-financial-context"
        data-align="center"
        data-wrap
      >
        <span>${startYear} to ${endYear}</span>
        <span
          title="Cumulative profit: current portfolio value minus net funding; the percentage is relative to deposits minus withdrawals"
        >
          Total P/L&nbsp;<span data-tone=${pnlVariant}
            >${formatSignedCurrency(summary.total_pnl_eur)}
            (${formatPercent(summary.total_pnl_pct, 1)} of net funding)</span
          ></span
        >
        ${this.renderNetDeposit(summary)}
        <span
          title="Since-inception money-weighted annual return used as the projection growth assumption"
        >
          Historical MWR p.a.&nbsp;<span data-tone=${runRateVariant}
            >${formatPercent(summary.annualized_total_pnl_pct, 1)}</span
          ></span
        >
      </div>
    `;
	}
	renderTable(checkpoints, expectedInflationPct) {
		if (checkpoints.length === 0) return b`<span>Not enough data yet</span>`;
		return b`
      <div
        class="fire-projection-scroll"
        role="region"
        aria-label="Year-by-year FIRE projections"
        tabindex="0"
      >
        <table
          class="fire-projection-table"
          aria-label="Portfolio value projections"
          style="border-spacing: 0; white-space: nowrap"
        >
          <thead>
            <tr>
              <th scope="col" style="text-align: left">Year</th>
              <th scope="col" style="text-align: right">Value</th>
              <th
                scope="col"
                aria-label="Projected net deposits"
                style="text-align: right"
              >
                Net deposits
              </th>
              <th
                scope="col"
                title="Initial monthly withdrawal if retiring that year: 4% of projected portfolio value divided by 12"
                style="text-align: right"
              >
                Monthly income
              </th>
              <th
                scope="col"
                title="Projected monthly withdrawal discounted by expected annual inflation to today's purchasing power"
                style="text-align: right"
              >
                Monthly income in today's money
              </th>
            </tr>
          </thead>
          <tbody>
            ${checkpoints.toReversed().map(({ date, point, projectedNetDeposits, income }) => b`
                <tr>
                  <th scope="row" style="font: inherit; text-align: left">
                    ${date.getUTCFullYear()}
                  </th>
                  <td style="text-align: right">
                    ${formatCurrency(point.projected_value_eur, "EUR", 0)}
                  </td>
                  <td style="text-align: right">
                    ${formatCurrency(projectedNetDeposits, "EUR", 0)}
                  </td>
                  <td style="text-align: right">
                    ${formatCurrency(income?.monthlyIncomeEur)}
                  </td>
                  <td style="text-align: right">
                    ${formatCurrency(income?.monthlyIncomeTodayEur)}
                  </td>
                </tr>
              `)}
          </tbody>
        </table>
      </div>
      <div style="color: var(--wa-color-text-quiet); font-size: 0.75em">
        Monthly income assumes retiring in that year and withdrawing 4% of the
        projected value annually, divided by 12. Today's money accounts for
        ${Number(expectedInflationPct).toFixed(2)}% expected annual inflation.
        The default is 2.11%, the mean Greece all-items HICP inflation for
        2016–2025 (Eurostat).
      </div>
    `;
	}
	renderProjection(data) {
		const checkpoints = this.projectionRows(data);
		if (checkpoints.length === 0) return b`<span>Not enough data yet</span>`;
		const startYear = String(data.summary.start_date).slice(0, 4);
		const endYear = checkpoints.at(-1).date.getUTCFullYear();
		return b`${this.renderFireCalculator(data)}
    ${this.renderMetrics(data.summary, startYear, endYear)}
    ${this.renderTable(checkpoints, data.expectedInflationPct)}`;
	}
	render() {
		let content;
		if (this.projection.loading && !this.projection.value) content = b`<span>Loading projection…</span>`;
		else if (this.projection.error) content = b`<span data-tone="error">Projection unavailable</span>`;
		else if (!this.projection.value?.summary || !this.projection.value?.projection?.length) content = b`<span>Not enough data yet</span>`;
		else content = this.renderProjection(this.projection.value);
		return b`
      <wa-card>
        <div slot="header" class="fire-header">
          <span>FIRE (Financial Independence, Retire Early)</span>
          ${this.projection.value ? this.renderFireAssumptions(this.projection.value) : ""}
        </div>
        ${this.fireAssumptionsError ? b`<div role="alert" data-tone="error">
              ${this.fireAssumptionsError}
            </div>` : ""}
        ${content}
      </wa-card>
    `;
	}
};
customElements.define("sentinel-portfolio-value", SentinelPortfolioValue);
// src/sentinel-securities.js
var COLUMN_SETTING_KEY = "ui_securities_table_columns";
var DEFAULT_COLUMNS = [
	"price",
	"security",
	"value",
	"pnl",
	"ideal",
	"deviation",
	"ai_score",
	"opportunity_score",
	"plan",
	"trade"
];
function plainPercent(value, fractionDigits = 1) {
	const number = Number(value);
	return Number.isFinite(number) ? `${number.toFixed(fractionDigits)}%` : "-";
}
function scorePercent(value, fractionDigits = 0) {
	const number = value == null ? NaN : Number(value);
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
var SentinelSecurities = class extends i$4 {
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
		window.addEventListener("sentinel-setting-changed", this.refreshForCashSetting);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-security-list-change", this.securityListChanged);
		window.removeEventListener("sentinel-setting-changed", this.refreshForCashSetting);
		super.disconnectedCallback();
	}
	refreshForCashSetting = (event) => {
		if (event.detail?.key === "simulated_cash_eur" || event.detail?.key === "trading_mode") this.securities.refresh();
	};
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
				case "deviation":
					result = left.current_allocation - left.ideal_allocation - (right.current_allocation - right.ideal_allocation);
					break;
				case "ai_score":
					if (left.ai_research_multiplier == null || right.ai_research_multiplier == null) return Number(left.ai_research_multiplier == null) - Number(right.ai_research_multiplier == null) || String(left.symbol).localeCompare(String(right.symbol));
					result = Number(left.ai_research_multiplier) - Number(right.ai_research_multiplier);
					break;
				case "opportunity_score":
					result = Number(left.opp_score ?? 0) - Number(right.opp_score ?? 0);
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
		let columns = DEFAULT_COLUMNS;
		if (Array.isArray(configured)) {
			const valid = configured.filter((column) => DEFAULT_COLUMNS.includes(column));
			if (valid.length > 0) columns = [
				...valid,
				"deviation",
				"ai_score",
				"opportunity_score"
			];
		} else if (Array.isArray(configured?.hidden)) columns = DEFAULT_COLUMNS.filter((column) => !configured.hidden.includes(column));
		const selected = new Set(columns);
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
		return "background: var(--wa-color-surface-lowered)";
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
		return variant ? b`<span data-tone=${variant}>${formatted}</span>` : formatted;
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
	async updateExecutionControl(event, security, field) {
		const value = event.currentTarget.checked ? 1 : 0;
		const previous = security[field];
		this.errorMessage = "";
		this.message = "";
		this.busyAction = `${field}:${security.symbol}`;
		this.updateLocalSecurity(security.symbol, { [field]: value });
		try {
			await putJson(`/api/securities/${encodeURIComponent(security.symbol)}`, { [field]: value });
			const label = {
				allow_buy: "buy permission",
				allow_sell: "sell permission",
				cooldown_enabled: "cool-off periods"
			}[field];
			this.message = `${security.symbol} ${label} updated`;
		} catch (error) {
			this.updateLocalSecurity(security.symbol, { [field]: previous });
			this.errorMessage = error.message;
		} finally {
			this.busyAction = "";
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
		this.querySelector("#add-security-dialog").open = true;
	}
	openColumnsDialog() {
		this.errorMessage = "";
		this.querySelector("#columns-dialog").open = true;
	}
	closeColumnsDialog() {
		this.querySelector("#columns-dialog").open = false;
	}
	async toggleColumn(event, column) {
		const previous = this.selectedColumns;
		const next = new Set(previous);
		if (event.currentTarget.checked) next.add(column);
		else next.delete(column);
		if (next.size === 0) {
			event.currentTarget.checked = true;
			this.errorMessage = "At least one table column must remain visible";
			return;
		}
		const selection = { hidden: DEFAULT_COLUMNS.filter((candidate) => !next.has(candidate)) };
		this.visibleColumns = selection;
		this.columnsBusy = true;
		this.errorMessage = "";
		try {
			await putJson(`/api/settings/${COLUMN_SETTING_KEY}`, { value: selection });
			this.columnSettings.value = {
				...this.columnSettings.value,
				[COLUMN_SETTING_KEY]: selection
			};
		} catch (error) {
			this.visibleColumns = { hidden: DEFAULT_COLUMNS.filter((candidate) => !previous.has(candidate)) };
			this.errorMessage = error.message;
		} finally {
			this.columnsBusy = false;
		}
	}
	closeAddDialog() {
		this.querySelector("#add-security-dialog").open = false;
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
		this.querySelector("#delete-security-dialog").open = true;
	}
	closeDeleteDialog() {
		this.querySelector("#delete-security-dialog").open = false;
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
      <div
        class="sentinel-layout securities-toolbar"
        data-align="center"
        data-justify="between"
        data-wrap
      >
        <div
          class="sentinel-layout securities-filters"
          data-align="center"
          data-wrap
        >
          <div class="sentinel-layout" data-align="center">
            <span class="securities-period-label" aria-hidden="true"
              >Period</span
            >
            <wa-radio-group
              size="xs"
              orientation="horizontal"
              aria-label="Security price period"
              .value=${this.period}
              @change=${this.changePeriod}
            >
              <wa-radio appearance="button" value="1M">1M</wa-radio>
              <wa-radio appearance="button" value="1Y">1Y</wa-radio>
              <wa-radio appearance="button" value="5Y">5Y</wa-radio>
              <wa-radio appearance="button" value="10Y">10Y</wa-radio>
            </wa-radio-group>
          </div>
          <wa-input
            class="securities-search"
            size="xs"
            type="search"
            aria-label="Search securities"
            placeholder="Search securities"
            @input=${this.changeSearch}
          ></wa-input>
        </div>
        <div class="sentinel-layout" data-align="center">
          <wa-button
            size="xs"
            appearance="plain"
            @click=${this.openColumnsDialog}
            >Columns</wa-button
          >
          <wa-button
            size="xs"
            appearance="outlined"
            @click=${this.openAddDialog}
            >Add Security</wa-button
          >
        </div>
      </div>
    `;
	}
	renderStats() {
		if (this.inactiveOnly) return "";
		const stats = this.stats;
		return b`
      <div class="securities-stats">
        ${stats.total} securities&nbsp;·&nbsp;${stats.positions}
        positions&nbsp;·&nbsp;
        <span data-tone="success">${stats.buys} buy signals</span>&nbsp;·&nbsp;
        <span data-tone="error">${stats.sells} sell signals</span>&nbsp;·&nbsp;
        ${this.visibleSecurities.length} shown
      </div>
    `;
	}
	renderSortableHeader(label, column) {
		return b`
      <th
        scope="col"
        aria-sort=${this.sortColumn === column ? this.sortReversed ? "descending" : "ascending" : "none"}
        style="text-align: left; vertical-align: middle"
      >
        <wa-button
          class="security-sort"
          size="xs"
          appearance="plain"
          @click=${() => this.changeSort(column)}
          >${label}<span aria-hidden="true" class="security-sort-marker"
            >${this.sortMarker(column)}</span
          ></wa-button
        >
      </th>
    `;
	}
	renderRecommendation(security) {
		const recommendation = security.recommendation;
		if (!recommendation) return b`<span>-</span>`;
		return b`<span data-tone=${recommendation.action === "buy" ? "success" : "error"}
      >${recommendation.action.toUpperCase()}
      ${formatCurrency(Math.abs(recommendation.value_delta_eur), "EUR")}</span
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
		return b`<sentinel-chart
      role="img"
      compact
      aria-label=${hasAverageCost ? `${security.symbol} price history; green above and red below average purchase price` : `${security.symbol} price history; no position`}
      min=${minimum}
      max=${maximum}
      threshold=${hasAverageCost ? averageCost : ""}
      .values=${values}
    ></sentinel-chart>`;
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
        <td style="vertical-align: middle">
          ${expanded ? b`<wa-button
                class="security-expand"
                size="xs"
                appearance="plain"
                aria-label="Collapse ${security.symbol}"
                aria-expanded="true"
                aria-controls=${detailsId}
                @click=${() => this.toggleExpanded(security.symbol)}
                >−</wa-button
              >` : b`<wa-button
                class="security-expand"
                size="xs"
                appearance="plain"
                aria-label="Expand ${security.symbol}"
                aria-expanded="false"
                aria-controls=${detailsId}
                @click=${() => this.toggleExpanded(security.symbol)}
                >+</wa-button
              >`}
        </td>
        ${this.columnVisible("price") ? b`<td style="vertical-align: middle; white-space: nowrap">
              ${this.renderPriceSparkline(security)}
            </td>` : ""}
        <th
          scope="row"
          style="font: inherit; text-align: left; vertical-align: middle; overflow-wrap: anywhere"
        >
          ${security.price_warning ? b`<span data-tone="warning">!&nbsp;</span>` : ""}<span class="security-symbol" style="white-space: nowrap"
            >${security.symbol}</span
          >
        </th>
        ${this.columnVisible("value") ? b`<td
              style="text-align: left; vertical-align: middle; overflow-wrap: anywhere"
            >
              ${security.has_position ? formatCurrency(security.value_eur, "EUR", 0) : "-"}
            </td>` : ""}
        ${this.columnVisible("pnl") ? b`<td
              style="text-align: left; vertical-align: middle; overflow-wrap: anywhere"
            >
              ${security.has_position ? b`${this.renderColored(security.profit_pct, formatPercent(security.profit_pct, 1))}&nbsp;${this.renderColored(security.profit_value_eur, formatCurrency(security.profit_value_eur, "EUR", 0))}` : "-"}
            </td>` : ""}
        ${this.columnVisible("ideal") ? b`<td style="text-align: left; vertical-align: middle">
              ${this.renderColored(idealDifference, plainPercent(security.ideal_allocation))}
            </td>` : ""}
        ${this.columnVisible("deviation") ? b`<td
              title="Current allocation minus ideal allocation; negative means underweight and positive means overweight"
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${formatPercent(-idealDifference, 1).replace("%", " pp")}
            </td>` : ""}
        ${this.columnVisible("ai_score") ? b`<td
              title="AI research rating: 0% avoid, 50% neutral, 100% prefer"
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${scorePercent(security.ai_research_multiplier, 1)}
            </td>` : ""}
        ${this.columnVisible("opportunity_score") ? b`<td
              title="Effective opportunity score after recent-dip memory and optional forecast adjustment"
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${scorePercent(security.opp_score, 1)}
            </td>` : ""}
        ${this.columnVisible("plan") ? b`<td
              style="text-align: left; vertical-align: middle; overflow-wrap: anywhere"
            >
              ${plainPercent(security.current_allocation)}
              ${allocationChange ? b`&nbsp;→&nbsp;${this.renderColored(security.post_plan_allocation - security.current_allocation, plainPercent(security.post_plan_allocation))}` : ""}
              <span>${this.renderRecommendation(security)}</span>
            </td>` : ""}
        ${this.columnVisible("trade") ? b`<td
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${this.inactiveOnly ? "Inactive" : b`<span class="trade-permissions"
                    ><wa-switch
                      size="xs"
                      aria-label="Allow buying ${security.symbol}"
                      .checked=${security.allow_buy === 1}
                      @change=${(event) => this.updateExecutionControl(event, security, "allow_buy")}
                      >B</wa-switch
                    ><wa-switch
                      size="xs"
                      aria-label="Allow selling ${security.symbol}"
                      .checked=${security.allow_sell === 1}
                      @change=${(event) => this.updateExecutionControl(event, security, "allow_sell")}
                      >S</wa-switch
                    ></span
                  >`}
            </td>` : ""}
      </tr>
      ${expanded ? this.renderExpandedRow(security, detailsId) : ""}
    `;
	}
	renderDetail(label, value) {
		return b`
      <div class="security-detail-field">
        <dt>${label}</dt>
        <dd>${value}</dd>
      </div>
    `;
	}
	renderPriceChart(security) {
		const values = (security.prices ?? []).map((price) => Number(price.close)).filter(Number.isFinite);
		if (values.length < 2) return b`<div>No price data</div>`;
		const averageCost = Number(security.avg_cost);
		const hasAverageCost = Boolean(security.has_position) && averageCost > 0;
		const scaleValues = hasAverageCost ? [...values, averageCost] : values;
		return b`<sentinel-chart
      role="img"
      aria-label="${security.symbol} price history"
      height="6"
      min=${Math.min(...scaleValues)}
      max=${Math.max(...scaleValues)}
      threshold=${hasAverageCost ? averageCost : ""}
      .values=${values}
    ></sentinel-chart>`;
	}
	renderExpandedRow(security, detailsId) {
		const aliasBusy = this.busyAction === `aliases:${security.symbol}`;
		const multiplier = security.ai_research_multiplier == null ? NaN : Number(security.ai_research_multiplier);
		return b`
      <tr id=${detailsId}>
        <td colspan=${this.selectedColumns.size + 1}>
          <wa-card
            class="security-details-panel"
            role="region"
            aria-label="${security.symbol} details"
          >
            ${this.renderPriceChart(security)}
            <dl class="security-detail-list">
              ${security.price_warning ? this.renderDetail("Warning", b`<span data-tone="warning"
                      >${security.price_warning}</span
                    >`) : ""}
              ${this.renderDetail("Name", security.name || "-")}
              ${this.renderDetail("Geography", security.geography || "-")}
              ${this.renderDetail("Industry", security.industry || "-")}
              ${this.renderDetail("Lot", security.min_lot ?? "-")}
              ${this.renderDetail("Quantity", security.quantity ?? 0)}
              ${this.renderDetail("Cool-off periods", b`<wa-switch
                  size="small"
                  aria-label="Cool-off periods for ${security.symbol}"
                  title="Apply global same-side and opposite-side cool-off periods to this security"
                  .checked=${security.cooldown_enabled !== 0}
                  ?disabled=${this.busyAction === `cooldown_enabled:${security.symbol}`}
                  @change=${(event) => this.updateExecutionControl(event, security, "cooldown_enabled")}
                  >Enabled</wa-switch
                >`)}
              ${this.renderDetail("Price", formatCurrency(security.current_price, security.currency))}
              ${this.renderDetail("Aliases", b`<div class="sentinel-layout" data-align="center" data-wrap>
                  <wa-input
                    size="small"
                    id="aliases-${safeId(security.symbol)}"
                    aria-label="Aliases for ${security.symbol}"
                    .value=${security.aliases ?? ""}
                    style="inline-size: 28ch; max-inline-size: 100%"
                  ></wa-input>
                  <wa-button
                    size="small"
                    ?disabled=${aliasBusy}
                    @click=${() => this.saveAliases(security)}
                    >Save aliases</wa-button
                  >
                </div>`)}
              ${this.renderDetail("Forecast 4w", this.renderColored(security.forecast_return_4w, scorePercent(security.forecast_return_4w, 1)))}
              ${this.renderDetail("Timing", scorePercent(security.forecast_score))}
              ${this.renderDetail("AI research", Number.isFinite(multiplier) ? multiplier.toFixed(2) : "-")}
              ${security.ai_research_multiplier_source ? this.renderDetail("Source", security.ai_research_multiplier_source) : ""}
              ${security.ai_research_multiplier_updated_at ? this.renderDetail("Updated", new Date(security.ai_research_multiplier_updated_at).toLocaleString()) : ""}
              ${security.ai_research_multiplier_analysis ? this.renderDetail("Analysis", security.ai_research_multiplier_analysis) : ""}
              ${this.renderDetail("Opportunity", scorePercent(security.opp_score, 1))}
              ${this.renderDetail("Dip", scorePercent(security.dip_score, 1))}
              ${this.renderDetail("Capitulation", scorePercent(security.capitulation_score, 1))}
              ${this.renderDetail("Cycle turn", security.cycle_turn ? "yes" : "no")}
              ${this.renderDetail("Freefall blocked", security.freefall_block ? "yes" : "no")}
              ${security.recommendation?.reason ? this.renderDetail("Plan", security.recommendation.reason) : ""}
              ${this.renderDetail("Actions", this.inactiveOnly ? b`<div
                      class="sentinel-layout"
                      data-align="center"
                      data-wrap
                    >
                      <wa-button
                        size="small"
                        ?disabled=${this.busyAction === `activate:${security.symbol}`}
                        @click=${() => this.activateSecurity(security)}
                        >Activate</wa-button
                      ><wa-button
                        size="small"
                        variant="danger"
                        title=${security.can_delete ? "Permanently delete unused security" : `Cannot delete: ${security.transaction_count || 0} historical transaction(s)`}
                        ?disabled=${!security.can_delete}
                        @click=${() => this.openDeleteDialog(security)}
                        >Delete Permanently</wa-button
                      >
                    </div>` : b`<wa-button
                      size="small"
                      variant="danger"
                      @click=${() => this.openDeleteDialog(security)}
                      >Remove</wa-button
                    >`)}
              ${this.inactiveOnly && !security.can_delete ? this.renderDetail("Deletion", `Permanent deletion is unavailable because this security has ${security.transaction_count || 0} historical transaction(s).`) : ""}
            </dl>
          </wa-card>
        </td>
      </tr>
    `;
	}
	renderTable() {
		const visible = this.visibleSecurities;
		const allExpanded = visible.length > 0 && visible.every((security) => this.expandedSymbols.has(security.symbol));
		if (visible.length === 0) return b`<div>No securities match the current controls</div>`;
		return b`
      <div class="securities-table-scroll">
        <table
          class="securities-table"
          aria-label=${this.inactiveOnly ? "Inactive Securities" : "Securities"}
          style="width: 100%; min-width: max-content; border-spacing: 0"
        >
          <thead>
            <tr>
              <th scope="col" style="text-align: left; vertical-align: middle">
                ${allExpanded ? b`<wa-button
                      class="security-expand"
                      size="xs"
                      appearance="plain"
                      aria-label="Collapse all securities"
                      @click=${this.toggleAll}
                      >−</wa-button
                    >` : b`<wa-button
                      class="security-expand"
                      size="xs"
                      appearance="plain"
                      aria-label="Expand all securities"
                      @click=${this.toggleAll}
                      >+</wa-button
                    >`}
              </th>
              ${this.columnVisible("price") ? b`<th
                    scope="col"
                    style="text-align: left; vertical-align: middle"
                  >
                    Price
                  </th>` : ""}
              ${this.renderSortableHeader("Security", "symbol")}
              ${this.columnVisible("value") ? this.renderSortableHeader("Value", "value") : ""}
              ${this.columnVisible("pnl") ? this.renderSortableHeader("P/L", "pnl") : ""}
              ${this.columnVisible("ideal") ? this.renderSortableHeader("Ideal", "ideal") : ""}
              ${this.columnVisible("deviation") ? this.renderSortableHeader("Deviation from ideal", "deviation") : ""}
              ${this.columnVisible("ai_score") ? this.renderSortableHeader("AI score", "ai_score") : ""}
              ${this.columnVisible("opportunity_score") ? this.renderSortableHeader("Opportunity score", "opportunity_score") : ""}
              ${this.columnVisible("plan") ? this.renderSortableHeader("Plan", "recommendation") : ""}
              ${this.columnVisible("trade") ? b`<th
                    scope="col"
                    style="text-align: left; vertical-align: middle"
                  >
                    <span aria-hidden="true"></span>${this.inactiveOnly ? "Status" : "Trade"}
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
      <wa-dialog
        class="sentinel-compact-dialog"
        id="columns-dialog"
        label="Columns"
      >
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("price")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "price")}
            >Price</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            checked
            disabled
            aria-label="Security column is always visible"
            >Security</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("value")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "value")}
            >Value</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("pnl")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "pnl")}
            >P/L</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("ideal")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "ideal")}
            >Ideal</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("deviation")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "deviation")}
            >Deviation from ideal</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("ai_score")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "ai_score")}
            >AI score</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("opportunity_score")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "opportunity_score")}
            >Opportunity score</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("plan")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "plan")}
            >Plan</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("trade")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "trade")}
            >Trade</wa-switch
          >
        </div>
        ${this.errorMessage ? b`<div>
              <span data-tone="error">${this.errorMessage}</span>
            </div>` : ""}
        <div>
          <wa-button size="small" @click=${this.closeColumnsDialog}
            >Done</wa-button
          >
        </div>
      </wa-dialog>
    `;
	}
	renderAddDialog() {
		return b`
      <wa-dialog
        class="sentinel-compact-dialog"
        id="add-security-dialog"
        label="Add Security"
      >
        <form @submit=${this.addSecurity}>
          <label>
            Symbol&nbsp;<wa-input
              size="small"
              id="add-security-symbol"
              aria-label="TraderNet security symbol"
              placeholder="AAPL.US"
              required
              ?disabled=${this.busyAction === "add"}
            ></wa-input>
          </label>
          <div>
            Geography and industry will be filled by the next metadata sync.
          </div>
          ${this.addError ? b`<div><span data-tone="error">${this.addError}</span></div>` : ""}
          <div>
            <wa-button
              size="small"
              type="submit"
              ?disabled=${this.busyAction === "add"}
              >Add Security</wa-button
            >&nbsp;
            <wa-button
              size="small"
              type="button"
              ?disabled=${this.busyAction === "add"}
              @click=${this.closeAddDialog}
              >Cancel</wa-button
            >
          </div>
        </form>
      </wa-dialog>
    `;
	}
	renderDeleteDialog() {
		const security = this.deleteCandidate;
		return b`
      <wa-dialog
        class="sentinel-compact-dialog"
        id="delete-security-dialog"
        label=${this.inactiveOnly ? "Delete Security Permanently" : "Remove Security"}
      >
        ${security ? b`
              <div>
                ${this.inactiveOnly ? `Permanently delete ${security.symbol}?` : `Remove ${security.symbol} from the active universe?`}
              </div>
              ${security.has_position ? b`<div>
                    <span data-tone="warning"
                      >Position: ${security.quantity} shares
                      (${formatCurrency(security.value_eur, "EUR")}). It will
                      remain managed, but new buys will be disabled.</span
                    >
                  </div>` : ""}
              ${this.errorMessage ? b`<div>
                    <span data-tone="error">${this.errorMessage}</span>
                  </div>` : ""}
              <div>
                <wa-button
                  size="small"
                  variant="danger"
                  ?disabled=${this.busyAction === `delete:${security.symbol}`}
                  @click=${this.deleteSecurity}
                  >${this.inactiveOnly ? "Delete Permanently" : "Remove"}</wa-button
                >&nbsp;
                <wa-button
                  size="small"
                  ?disabled=${this.busyAction === `delete:${security.symbol}`}
                  @click=${this.closeDeleteDialog}
                  >Cancel</wa-button
                >
              </div>
            ` : ""}
      </wa-dialog>
    `;
	}
	render() {
		let content;
		if (this.securities.loading && !this.securities.value) content = b`<span>Loading securities…</span>`;
		else if (this.securities.error) content = b`<span data-tone="error"
        >Securities unavailable: ${this.securities.error.message}</span
      >`;
		else content = b`
        ${this.renderControls()} ${this.renderStats()}
        ${this.message ? b`<div><span data-tone="success">${this.message}</span></div>` : ""}
        ${this.errorMessage ? b`<div><span data-tone="error">${this.errorMessage}</span></div>` : ""}
        ${this.renderTable()}
      `;
		return b`
      ${this.bare ? content : b`<wa-card
            ><span slot="header"
              >${this.inactiveOnly ? "Inactive Securities" : "Securities"}</span
            >${content}</wa-card
          >`}
      ${this.inactiveOnly ? "" : b`${this.renderColumnsDialog()} ${this.renderAddDialog()}`}
      ${this.renderDeleteDialog()}
    `;
	}
};
customElements.define("sentinel-securities", SentinelSecurities);
// src/widget-state.js
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
// src/sentinel-inactive-securities.js
var SentinelInactiveSecurities = class extends i$4 {
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
      <wa-details
        ?open=${!widgetCollapsed("inactive-securities")}
        @wa-after-show=${this.toggleDetails}
        @wa-after-hide=${this.toggleDetails}
      >
        <span slot="summary"> Inactive Securities (${count}) </span>
        ${this.detailsRequested ? b`<wa-card>
              <sentinel-securities
                inactive-only
                bare
                .period=${this.period}
              ></sentinel-securities>
            </wa-card>` : ""}
      </wa-details>
    `;
	}
};
customElements.define("sentinel-inactive-securities", SentinelInactiveSecurities);
// src/sentinel-risk-return.js
function clamp01(value) {
	if (!Number.isFinite(value)) return 0;
	return Math.max(0, Math.min(1, value));
}
function percent(value, digits = 1) {
	if (value === null || value === void 0 || Number.isNaN(value)) return "—";
	return `${(value * 100).toFixed(digits)}%`;
}
function number(value, digits = 2) {
	if (value === null || value === void 0 || Number.isNaN(value)) return "—";
	return Number(value).toFixed(digits);
}
var SentinelRiskReturn = class extends i$4 {
	composition = new LiveResource(this, (signal) => getJson("/api/portfolio/composition", { signal }), { interval: 3e5 });
	createRenderRoot() {
		return this;
	}
	storeCollapsed(event) {
		if (event.target === event.currentTarget) storeWidgetCollapsed("risk-return", !event.currentTarget.open);
	}
	metricRows(metrics) {
		const rows = [
			{
				label: "Last year",
				subLabel: "1Y return — money made (or lost) after subtracting deposits",
				value: metrics.return_1y,
				formatted: percent(metrics.return_1y),
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
				formatted: percent(metrics.return_since_inception_cagr),
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
				formatted: percent(metrics.volatility),
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
				formatted: percent(metrics.max_drawdown),
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
			const coverage = `covers ${percent(metrics.home_coverage_pct, 0)} of holdings`;
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
				formatted: percent(metrics.alpha_1y_vs_home),
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
		if (row.goodDirection === "neutral" || !Number.isFinite(row.value)) return "var(--wa-color-text-normal)";
		return (row.goodDirection === "high" ? row.value >= row.reference : row.value <= row.reference) ? "var(--wa-color-success-on-normal)" : "var(--wa-color-danger-on-normal)";
	}
	renderMetric(row, index) {
		const span = row.max - row.min;
		const referencePosition = span > 0 ? clamp01((row.reference - row.min) / span) : .5;
		const valuePosition = span > 0 && Number.isFinite(row.value) ? clamp01((row.value - row.min) / span) : referencePosition;
		const color = this.metricColor(row);
		const tooltipTarget = `risk-return-metric-${index}`;
		return b`
      <div class="risk-metric">
        <dt>
          <wa-button
            id=${tooltipTarget}
            class="risk-metric-label"
            size="xs"
            appearance="plain"
          >
            ${row.label}
          </wa-button>
          <wa-tooltip for=${tooltipTarget}>
            <div>${row.subLabel}</div>
            <div>
              Scale ${row.minLabel} to ${row.maxLabel} · Marker
              ${row.referenceLabel}
            </div>
          </wa-tooltip>
        </dt>
        <dd>
          <span style="color: ${color}">${row.formatted}</span>
          <span
            class="risk-metric-gauge"
            aria-hidden="true"
            style="
              --risk-reference: ${referencePosition * 100}%;
              --risk-value: ${valuePosition * 100}%;
              --risk-value-color: ${color};
            "
          ></span>
        </dd>
      </div>
    `;
	}
	renderHomeMarkets(data) {
		const markets = data.home_markets || [];
		if (markets.length === 0 || !(data.metrics.home_coverage_pct > 0)) return b`<p class="risk-market-empty">
        Benchmarks not yet synced — home-market comparison will populate on next
        sync cycle.
      </p>`;
		return b`
      <table class="risk-market-table">
        <caption>
          Home markets
        </caption>
        <thead>
          <tr>
            <th scope="col">Market</th>
            <th scope="col">Weight</th>
            <th scope="col">Alpha</th>
            <th scope="col">Beta</th>
          </tr>
        </thead>
        <tbody>
          ${markets.map((market) => b`
              <tr>
                <th scope="row">${market.group}</th>
                <td>${percent(market.weight_pct, 0)}</td>
                <td
                  data-tone=${!Number.isFinite(market.alpha_1y) ? "" : market.alpha_1y >= 0 ? "success" : "error"}
                >
                  ${percent(market.alpha_1y)}
                </td>
                <td>${number(market.beta)}</td>
              </tr>
            `)}
        </tbody>
      </table>
    `;
	}
	render() {
		const data = this.composition.value;
		if (this.composition.loading && !data || this.composition.error || !data?.metrics) return "";
		return b`
      <wa-details
        ?open=${!widgetCollapsed("risk-return")}
        @wa-after-show=${this.storeCollapsed}
        @wa-after-hide=${this.storeCollapsed}
      >
        <span slot="summary">Risk / Return</span>
        <div class="risk-return-layout">
          <dl class="risk-metrics">
            ${this.metricRows(data.metrics).map((row, index) => this.renderMetric(row, index))}
          </dl>
          ${this.renderHomeMarkets(data)}
        </div>
      </wa-details>
    `;
	}
};
customElements.define("sentinel-risk-return", SentinelRiskReturn);
// node_modules/lit-html/directives/repeat.js
/**
* @license
* Copyright 2017 Google LLC
* SPDX-License-Identifier: BSD-3-Clause
*/
var u = (e, s, t) => {
	const r = /* @__PURE__ */ new Map();
	for (let l = s; l <= t; l++) r.set(e[l], l);
	return r;
};
var c = e$4(class extends i$3 {
	constructor(e) {
		if (super(e), e.type !== t$1.CHILD) throw Error("repeat() can only be used in text expressions");
	}
	dt(e, s, t) {
		let r;
		void 0 === t ? t = s : void 0 !== s && (r = s);
		const l = [], o = [];
		let i = 0;
		for (const s of e) l[i] = r ? r(s, i) : i, o[i] = t(s, i), i++;
		return {
			values: o,
			keys: l
		};
	}
	render(e, s, t) {
		return this.dt(e, s, t).values;
	}
	update(s, [t, r, c]) {
		const d = M(s), { values: p$3, keys: a } = this.dt(t, r, c);
		if (!Array.isArray(d)) return this.ut = a, p$3;
		const h$3 = this.ut ??= [], v$2 = [];
		let m, y, x = 0, j = d.length - 1, k = 0, w = p$3.length - 1;
		for (; x <= j && k <= w;) if (null === d[x]) x++;
		else if (null === d[j]) j--;
		else if (h$3[x] === a[k]) v$2[k] = u$1(d[x], p$3[k]), x++, k++;
		else if (h$3[j] === a[w]) v$2[w] = u$1(d[j], p$3[w]), j--, w--;
		else if (h$3[x] === a[w]) v$2[w] = u$1(d[x], p$3[w]), v(s, v$2[w + 1], d[x]), x++, w--;
		else if (h$3[j] === a[k]) v$2[k] = u$1(d[j], p$3[k]), v(s, d[x], d[j]), j--, k++;
		else if (void 0 === m && (m = u(a, k, w), y = u(h$3, x, j)), m.has(h$3[x])) if (m.has(h$3[j])) {
			const e = y.get(a[k]), t = void 0 !== e ? d[e] : null;
			if (null === t) {
				const e = v(s, d[x]);
				u$1(e, p$3[k]), v$2[k] = e;
			} else v$2[k] = u$1(t, p$3[k]), v(s, d[x], t), d[e] = null;
			k++;
		} else h(d[j]), j--;
		else h(d[x]), x++;
		for (; k <= w;) {
			const e = v(s, v$2[w + 1]);
			u$1(e, p$3[k]), v$2[k++] = e;
		}
		for (; x <= j;) {
			const e = d[x++];
			null !== e && h(e);
		}
		return this.ut = a, p(s, v$2), E;
	}
});
// src/sentinel-security-allocation.js
var TARGET_SERIES = [{
	key: "targetWeight",
	style: "target",
	label: "12-month target"
}, {
	key: "idealWeight",
	style: "ideal",
	label: "Ideal allocation"
}];
function weightFor(value, total) {
	return total > 0 && Number.isFinite(value) ? value / total * 100 : null;
}
function valueFor(weight, total) {
	return total > 0 && Number.isFinite(weight) ? weight / 100 * total : null;
}
function weightLabel(weight) {
	return Number.isFinite(weight) ? `${Number(weight.toFixed(2))}%` : "—";
}
function scaleTicks(highest) {
	const interval = Math.max((highest || 4) / 4, .01);
	const magnitude = 10 ** Math.floor(Math.log10(interval));
	const step = [
		1,
		1.25,
		1.5,
		2,
		2.5,
		3,
		5,
		10
	].find((n) => n * magnitude >= interval) * magnitude;
	return Array.from({ length: Math.ceil((highest || 4) / step) + 1 }, (_, index) => index * step);
}
function targetPath(rows, key, scale) {
	let command = "M";
	return rows.map((row, index) => {
		if (!Number.isFinite(row[key])) {
			command = "M";
			return "";
		}
		const point = `${command}${scale(row[key])},${index + .5}`;
		command = "L";
		return point;
	}).join(" ");
}
var SentinelSecurityAllocation = class extends i$4 {
	static properties = {
		sortBy: { state: true },
		showTargets: { state: true }
	};
	constructor() {
		super();
		this.sortBy = "currentWeight";
		this.showTargets = true;
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
		window.addEventListener("sentinel-setting-changed", this.refreshForCashSetting);
	}
	disconnectedCallback() {
		window.removeEventListener("sentinel-setting-changed", this.refreshForCashSetting);
		super.disconnectedCallback();
	}
	refreshForCashSetting = (event) => {
		if (event.detail?.key === "simulated_cash_eur" || event.detail?.key === "trading_mode") this.allocation.refresh();
	};
	storeCollapsed(event) {
		if (event.target === event.currentTarget) storeWidgetCollapsed("security-allocation", !event.currentTarget.open);
	}
	get rows() {
		const { securities = [], planner = {} } = this.allocation.value ?? {};
		const { plan, summary } = planner;
		const targets = new Map((plan?.targets ?? []).map((target) => [target.symbol, target]));
		const recommendations = new Map((planner.recommendations ?? []).map((trade) => [trade.symbol, trade]));
		const total = plan?.current_total_value_eur;
		const terminal = plan?.terminal_portfolio_value_eur;
		const afterPlanTotal = total - (summary?.total_fees ?? 0);
		const rows = [];
		for (const security of securities) {
			const target = targets.get(security.symbol);
			const trade = recommendations.get(security.symbol);
			const current = security.value_eur ?? 0;
			const delta = trade?.value_delta_eur ?? 0;
			const targetWeight = target?.target_allocation_pct;
			const idealWeight = target?.model_target_allocation_pct ?? security.ideal_allocation;
			const hasPosition = security.has_position && current > 0;
			const hasTarget = this.showTargets && (targetWeight > 0 || idealWeight > 0);
			if (!hasPosition && !delta && !hasTarget) continue;
			const planned = Math.max(0, current + delta);
			const currentWeight = security.current_allocation ?? weightFor(current, total) ?? 0;
			rows.push({
				id: `allocation-security-${encodeURIComponent(security.symbol)}`,
				symbol: security.symbol,
				current,
				planned,
				delta,
				currentWeight,
				plannedWeight: security.post_plan_allocation ?? weightFor(planned, afterPlanTotal) ?? currentWeight,
				targetWeight,
				targetValue: target?.target_value_eur,
				idealWeight,
				idealValue: target?.model_target_value_eur ?? valueFor(idealWeight, terminal),
				targetGap: target?.gap_eur,
				quantityDelta: target?.quantity_delta,
				sellLocked: target?.sell_locked
			});
		}
		const cash = plan?.current_cash_eur ?? 0;
		const plannedCash = Math.max(0, summary?.cash_after_plan ?? cash);
		const targetCash = plan?.target_cash_value_eur;
		if (cash > 0 || plannedCash > 0 || this.showTargets && targetCash > 0) {
			const idealCashWeight = plan?.targets ? Math.max(0, 100 - plan.targets.reduce((sum, target) => sum + (target.model_target_allocation_pct ?? target.target_allocation_pct ?? 0), 0)) : null;
			const currentWeight = weightFor(cash, total) ?? 0;
			rows.push({
				id: "allocation-cash",
				symbol: "CASH",
				current: cash,
				planned: plannedCash,
				delta: plannedCash - cash,
				currentWeight,
				plannedWeight: weightFor(plannedCash, afterPlanTotal) ?? currentWeight,
				targetWeight: plan?.target_cash_allocation_pct,
				targetValue: targetCash,
				idealWeight: idealCashWeight,
				idealValue: valueFor(idealCashWeight, terminal),
				targetGap: plan?.cash_gap_eur
			});
		}
		return rows.sort((left, right) => (right[this.sortBy] ?? -1) - (left[this.sortBy] ?? -1) || right.currentWeight - left.currentWeight || left.symbol.localeCompare(right.symbol));
	}
	renderBar(row, index, scale) {
		const base = row.delta < 0 ? Math.min(row.currentWeight, row.plannedWeight) : row.currentWeight;
		const end = row.delta > 0 ? Math.max(row.currentWeight, row.plannedWeight) : row.currentWeight;
		return b`
      <div
        class="allocation-bar"
        style="grid-row: ${index + 1}; --allocation-bar-base: ${scale(base)}%"
      >
        <span class="allocation-held"></span>
        ${end > base ? b`<span
              class=${row.delta > 0 ? "allocation-add" : "allocation-remove"}
              style="inline-size: ${scale(end - base)}%"
            ></span>` : ""}
      </div>
    `;
	}
	renderChart(rows) {
		const series = this.showTargets ? TARGET_SERIES : [];
		const tooltipTrigger = globalThis.matchMedia?.("(hover: none)").matches ? "click" : "hover focus";
		const ticks = scaleTicks(Math.max(0, ...rows.map((row) => Math.max(row.currentWeight, row.plannedWeight, ...series.map(({ key }) => row[key] ?? 0)))));
		const scale = (weight) => weight / ticks.at(-1) * 100;
		return b`
      <figure
        class="allocation-figure"
        style="--allocation-count: ${rows.length}"
      >
        <figcaption>Portfolio weight</figcaption>
        <div class="allocation-axis" aria-hidden="true">
          ${ticks.map((tick) => b`<span style="inset-inline-start: ${scale(tick)}%">
                ${weightLabel(tick)}
              </span>`)}
        </div>
        <div class="allocation-tickers">
          ${c(rows, (row) => row.id, (row) => b`<wa-button id=${row.id} appearance="plain" size="small"
                >${row.symbol}</wa-button
              >`)}
        </div>
        <div class="allocation-plot" aria-hidden="true">
          ${ticks.map((tick) => b`<span
                class="allocation-gridline"
                style="inset-inline-start: ${scale(tick)}%"
              ></span>`)}
          ${rows.map((row, index) => this.renderBar(row, index, scale))}
          ${series.length ? w`<svg
                class="allocation-lines"
                viewBox="0 0 100 ${rows.length}"
                preserveAspectRatio="none"
              >
                ${series.map(({ key, style }) => w`<path
                    class="allocation-${style}"
                    d=${targetPath(rows, key, scale)}
                  />`)}
              </svg>` : ""}
          ${series.length ? rows.map((row, index) => b`<div
                    class="allocation-points"
                    style="grid-row: ${index + 1}"
                  >
                    ${series.map(({ key, style }) => Number.isFinite(row[key]) ? b`<span
                            class="allocation-point allocation-${style}"
                            style="inset-inline-start: ${scale(row[key])}%"
                          ></span>` : "")}
                  </div>`) : ""}
        </div>
        ${c(rows, (row) => row.id, (row) => this.renderTooltip(row, tooltipTrigger))}
      </figure>
    `;
	}
	renderTooltip(row, trigger) {
		const entries = [[
			"Current",
			row.currentWeight,
			row.current
		], [
			"After plan",
			row.plannedWeight,
			row.planned
		]];
		if (this.showTargets) entries.push([
			"12-month target",
			row.targetWeight,
			row.targetValue
		], [
			"Ideal allocation",
			row.idealWeight,
			row.idealValue
		]);
		return b`
      <wa-tooltip for=${row.id} trigger=${trigger}>
        <strong>${row.symbol}</strong>
        <dl class="allocation-tooltip-values">
          ${entries.map(([label, weight, value]) => b`
              <dt>${label}</dt>
              <dd>${weightLabel(weight)}</dd>
              <dd>${Number.isFinite(value) ? formatCurrency(value) : "—"}</dd>
            `)}
        </dl>
        ${this.showTargets && Number.isFinite(row.targetGap) ? b`<div>
              Target gap
              ${row.targetGap > 0 ? "+" : ""}${formatCurrency(row.targetGap)}
              ${row.quantityDelta ? b` ·
                  ${row.quantityDelta > 0 ? "+" : ""}${row.quantityDelta.toLocaleString()}
                  shares` : ""}
            </div>` : ""}
        ${this.showTargets && row.sellLocked ? b`<div>Selling disabled</div>` : ""}
      </wa-tooltip>
    `;
	}
	renderLegend() {
		return b`
      <ul class="allocation-legend" aria-label="Chart legend">
        ${[
			{
				style: "held",
				label: "Current holding"
			},
			{
				style: "add",
				label: "Plan increase"
			},
			{
				style: "remove",
				label: "Plan decrease"
			},
			...this.showTargets ? TARGET_SERIES : []
		].map(({ style, label }) => b`<li>
              <span
                class="allocation-swatch allocation-${style}"
                aria-hidden="true"
              ></span>
              ${label}
            </li>`)}
      </ul>
    `;
	}
	render() {
		if (this.allocation.error || !this.allocation.value) return "";
		const rows = this.rows;
		return b`
      <wa-details
        ?open=${!widgetCollapsed("security-allocation")}
        @wa-after-show=${this.storeCollapsed}
        @wa-after-hide=${this.storeCollapsed}
      >
        <span slot="summary">Security Allocation</span>
        <div class="allocation-toolbar">
          ${this.renderLegend()}
          <div class="allocation-controls">
            <wa-select
              size="small"
              aria-label="Sort securities by"
              .value=${this.sortBy}
              @change=${(event) => {
			this.sortBy = event.currentTarget.value;
		}}
            >
              <wa-option value="currentWeight">Current weight</wa-option>
              <wa-option value="targetWeight">12-month target</wa-option>
              <wa-option value="idealWeight">Ideal allocation</wa-option>
            </wa-select>
            <wa-switch
              size="small"
              .checked=${this.showTargets}
              @change=${(event) => {
			this.showTargets = event.currentTarget.checked;
		}}
              >Show targets</wa-switch
            >
          </div>
        </div>
        ${rows.length ? this.renderChart(rows) : b`<p class="allocation-empty">No allocation data available</p>`}
      </wa-details>
    `;
	}
};
customElements.define("sentinel-security-allocation", SentinelSecurityAllocation);
// src/sentinel-status-bar.js
var SentinelStatusBar = class extends i$4 {
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
		if (this.health.error) return b`<span data-tone="error">broker: unavailable</span>`;
		if (!this.health.value) return b`<span>broker: connecting</span>`;
		return this.health.value.broker_connected ? b`<span data-tone="success">broker: connected</span>` : b`<span data-tone="error">broker: disconnected</span>`;
	}
	renderMarkets() {
		if (this.markets.error || this.markets.value?.markets?.length === 0) return b`<span data-tone="error">markets unavailable</span>`;
		if (!this.markets.value) return b`<span>markets loading</span>`;
		return b`
      <div class="sentinel-layout" data-align="center" data-wrap>
        ${this.markets.value.markets.map((market) => b`
            <span data-tone=${market.is_open ? "success" : "error"}
              >${market.name}</span
            >
          `)}
      </div>
    `;
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
			window.dispatchEvent(new CustomEvent("sentinel-setting-changed", { detail: {
				key: "trading_mode",
				value: this.selectedMode
			} }));
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
        <div class="sentinel-toolbar">
          <div
            class="sentinel-layout sentinel-status-line"
            data-align="center"
            data-wrap
          >
            <wa-radio-group
              size="xs"
              orientation="horizontal"
              aria-label="Trading mode"
              .value=${this.selectedMode ?? this.health.value?.trading_mode ?? "research"}
              ?disabled=${this.modePending}
              @change=${this.changeMode}
            >
              <wa-radio appearance="button" value="research">Research</wa-radio>
              <wa-radio appearance="button" value="live">Live</wa-radio>
            </wa-radio-group>

            ${this.renderBrokerStatus()} ${this.renderMarkets()}
            <span class="sentinel-version">Sentinel ${this.versionText}</span>
          </div>
        </div>
      </footer>
    `;
	}
};
customElements.define("sentinel-status-bar", SentinelStatusBar);
// src/sentinel-app.js
var SentinelApp = class extends i$4 {
	createRenderRoot() {
		return this;
	}
	render() {
		return b`
      <div
        class="sentinel-layout"
        data-direction="column"
        style="height: 100dvh; overflow: hidden"
      >
        <sentinel-header
          style="display: block; flex: 0 0 auto"
        ></sentinel-header>
        <main style="flex: 1 1 auto; min-height: 0; overflow: auto">
          <sentinel-portfolio-status
            style="display: block"
          ></sentinel-portfolio-status>
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
      </div>
    `;
	}
};
customElements.define("sentinel-app", SentinelApp);
// src/main.js
var darkScheme = window.matchMedia("(prefers-color-scheme: dark)");
function applyColorScheme() {
	document.documentElement.classList.toggle("wa-dark", darkScheme.matches);
}
darkScheme.addEventListener("change", applyColorScheme);
applyColorScheme();
export { __vitePreload as t };
