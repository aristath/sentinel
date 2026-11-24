const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/dist-BxC8nqPU.js","assets/dist-CJeZrQcM.js","assets/dist-CwPU8lnB.js","assets/dist-CpCORA7h.js","assets/dist-WpEfrNtY.js","assets/dist-pcGzLYMK.js","assets/dist-1P8onANw.js","assets/dist-CQ1fCqb8.js","assets/dist-CLvdafbe.js","assets/dist-G60vk3xx.js","assets/dist-D8qfJt65.js","assets/dist-3filMJMm.js","assets/dist-DFGEmTdM.js","assets/dist-Cb068DGT.js","assets/dist-UTM6z0uj.js","assets/dist-CaG0rY7y.js","assets/dist-C6dge6U9.js","assets/dist-CcHO7GVS.js","assets/dist-CdSSk6At.js","assets/dist-BD8HEXQv.js","assets/dist-co3cIu65.js","assets/dist-ezMgdHqZ.js","assets/dist-CG6X9yG7.js","assets/dockerfile-BKceAHtN.js","assets/simple-mode-Ch2FrE6Z.js","assets/factor-CJwPu3dp.js","assets/nsis-OBNRHa9B.js","assets/pug-BOEIvkN-.js","assets/javascript-Bgsg0Ond.js","assets/dist-B_LqJYNN.js","assets/dist-gubZSbzE.js"])))=>i.map(i=>d[i]);
import { LanguageDescription, LanguageSupport, StreamLanguage } from "./dist-CJeZrQcM.js";
import { t as __vitePreload } from "./index-RXO6gJIB.js";
// node_modules/@codemirror/language-data/dist/index.js
function legacy(parser) {
	return new LanguageSupport(StreamLanguage.define(parser));
}
function sql(dialectName) {
	return __vitePreload(() => import("./dist-BxC8nqPU.js").then((m) => m.sql({ dialect: m[dialectName] })), __vite__mapDeps([0,1,2,3,4]));
}
/**
An array of language descriptions for known language packages.
*/
var languages = [
	/*@__PURE__*/ LanguageDescription.of({
		name: "C",
		extensions: [
			"c",
			"h",
			"ino"
		],
		load() {
			return __vitePreload(() => import("./dist-pcGzLYMK.js").then((m) => m.cpp()), __vite__mapDeps([5,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "C++",
		alias: ["cpp"],
		extensions: [
			"cpp",
			"c++",
			"cc",
			"cxx",
			"hpp",
			"h++",
			"hh",
			"hxx"
		],
		load() {
			return __vitePreload(() => import("./dist-pcGzLYMK.js").then((m) => m.cpp()), __vite__mapDeps([5,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "CQL",
		alias: ["cassandra"],
		extensions: ["cql"],
		load() {
			return sql("Cassandra");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "CSS",
		extensions: ["css"],
		load() {
			return __vitePreload(() => import("./dist-1P8onANw.js").then((n) => n.i).then((m) => m.css()), __vite__mapDeps([6,2,3,1]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Go",
		extensions: ["go"],
		load() {
			return __vitePreload(() => import("./dist-CQ1fCqb8.js").then((m) => m.go()), __vite__mapDeps([7,3,1,2,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "HTML",
		alias: ["xhtml"],
		extensions: [
			"html",
			"htm",
			"handlebars",
			"hbs"
		],
		load() {
			return __vitePreload(() => import("./dist-CLvdafbe.js").then((m) => m.html()), __vite__mapDeps([8,3,1,2,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Java",
		extensions: ["java"],
		load() {
			return __vitePreload(() => import("./dist-D8qfJt65.js").then((m) => m.java()), __vite__mapDeps([10,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JavaScript",
		alias: [
			"ecmascript",
			"js",
			"node"
		],
		extensions: [
			"js",
			"mjs",
			"cjs"
		],
		load() {
			return __vitePreload(() => import("./dist-G60vk3xx.js").then((n) => n.t).then((m) => m.javascript()), __vite__mapDeps([9,3,1,2,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Jinja",
		extensions: [
			"j2",
			"jinja",
			"jinja2"
		],
		load() {
			return __vitePreload(() => import("./dist-3filMJMm.js").then((m) => m.jinja()), __vite__mapDeps([11,1,2,8,3,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JSON",
		alias: ["json5"],
		extensions: ["json", "map"],
		load() {
			return __vitePreload(() => import("./dist-DFGEmTdM.js").then((m) => m.json()), __vite__mapDeps([12,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JSX",
		extensions: ["jsx"],
		load() {
			return __vitePreload(() => import("./dist-G60vk3xx.js").then((n) => n.t).then((m) => m.javascript({ jsx: true })), __vite__mapDeps([9,3,1,2,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "LESS",
		extensions: ["less"],
		load() {
			return __vitePreload(() => import("./dist-Cb068DGT.js").then((m) => m.less()), __vite__mapDeps([13,1,2,6,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Liquid",
		extensions: ["liquid"],
		load() {
			return __vitePreload(() => import("./dist-UTM6z0uj.js").then((m) => m.liquid()), __vite__mapDeps([14,1,2,8,3,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MariaDB SQL",
		load() {
			return sql("MariaSQL");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Markdown",
		extensions: [
			"md",
			"markdown",
			"mkd"
		],
		load() {
			return __vitePreload(() => import("./dist-CaG0rY7y.js").then((m) => m.markdown()), __vite__mapDeps([15,2,1,4,8,3,6,9]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MS SQL",
		load() {
			return sql("MSSQL");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MySQL",
		load() {
			return sql("MySQL");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "PHP",
		extensions: [
			"php",
			"php3",
			"php4",
			"php5",
			"php7",
			"phtml"
		],
		load() {
			return __vitePreload(() => import("./dist-C6dge6U9.js").then((m) => m.php()), __vite__mapDeps([16,3,1,2,8,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "PLSQL",
		extensions: ["pls"],
		load() {
			return sql("PLSQL");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "PostgreSQL",
		load() {
			return sql("PostgreSQL");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Python",
		extensions: [
			"BUILD",
			"bzl",
			"py",
			"pyw"
		],
		filename: /^(BUCK|BUILD)$/,
		load() {
			return __vitePreload(() => import("./dist-CcHO7GVS.js").then((m) => m.python()), __vite__mapDeps([17,3,1,2,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Rust",
		extensions: ["rs"],
		load() {
			return __vitePreload(() => import("./dist-CdSSk6At.js").then((m) => m.rust()), __vite__mapDeps([18,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Sass",
		extensions: ["sass"],
		load() {
			return __vitePreload(() => import("./dist-BD8HEXQv.js").then((m) => m.sass({ indented: true })), __vite__mapDeps([19,3,1,2,6]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SCSS",
		extensions: ["scss"],
		load() {
			return __vitePreload(() => import("./dist-BD8HEXQv.js").then((m) => m.sass()), __vite__mapDeps([19,3,1,2,6]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SQL",
		extensions: ["sql"],
		load() {
			return sql("StandardSQL");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SQLite",
		load() {
			return sql("SQLite");
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TSX",
		extensions: ["tsx"],
		load() {
			return __vitePreload(() => import("./dist-G60vk3xx.js").then((n) => n.t).then((m) => m.javascript({
				jsx: true,
				typescript: true
			})), __vite__mapDeps([9,3,1,2,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TypeScript",
		alias: ["ts"],
		extensions: [
			"ts",
			"mts",
			"cts"
		],
		load() {
			return __vitePreload(() => import("./dist-G60vk3xx.js").then((n) => n.t).then((m) => m.javascript({ typescript: true })), __vite__mapDeps([9,3,1,2,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "WebAssembly",
		extensions: ["wat", "wast"],
		load() {
			return __vitePreload(() => import("./dist-co3cIu65.js").then((m) => m.wast()), __vite__mapDeps([20,1,2,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "XML",
		alias: [
			"rss",
			"wsdl",
			"xsd"
		],
		extensions: [
			"xml",
			"xsl",
			"xsd",
			"svg"
		],
		load() {
			return __vitePreload(() => import("./dist-ezMgdHqZ.js").then((m) => m.xml()), __vite__mapDeps([21,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "YAML",
		alias: ["yml"],
		extensions: ["yaml", "yml"],
		load() {
			return __vitePreload(() => import("./dist-CG6X9yG7.js").then((m) => m.yaml()), __vite__mapDeps([22,3,1,2]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "APL",
		extensions: ["dyalog", "apl"],
		load() {
			return __vitePreload(() => import("./apl-pAUjKRa-.js").then((m) => legacy(m.apl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "PGP",
		alias: ["asciiarmor"],
		extensions: [
			"asc",
			"pgp",
			"sig"
		],
		load() {
			return __vitePreload(() => import("./asciiarmor-OoUmpQ10.js").then((m) => legacy(m.asciiArmor)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ASN.1",
		extensions: ["asn", "asn1"],
		load() {
			return __vitePreload(() => import("./asn1-BmIrhlwK.js").then((m) => legacy(m.asn1({}))), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Asterisk",
		filename: /^extensions\.conf$/i,
		load() {
			return __vitePreload(() => import("./asterisk-BElHvODl.js").then((m) => legacy(m.asterisk)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Brainfuck",
		extensions: ["b", "bf"],
		load() {
			return __vitePreload(() => import("./brainfuck-D13xYRsf.js").then((m) => legacy(m.brainfuck)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Cobol",
		extensions: ["cob", "cpy"],
		load() {
			return __vitePreload(() => import("./cobol-BpHe5oeu.js").then((m) => legacy(m.cobol)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "C#",
		alias: ["csharp", "cs"],
		extensions: ["cs"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.csharp)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Clojure",
		extensions: [
			"clj",
			"cljc",
			"cljx"
		],
		load() {
			return __vitePreload(() => import("./clojure-Cuc-6ayA.js").then((m) => legacy(m.clojure)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ClojureScript",
		extensions: ["cljs"],
		load() {
			return __vitePreload(() => import("./clojure-Cuc-6ayA.js").then((m) => legacy(m.clojure)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Closure Stylesheets (GSS)",
		extensions: ["gss"],
		load() {
			return __vitePreload(() => import("./css-7Yruh3G2.js").then((m) => legacy(m.gss)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "CMake",
		extensions: ["cmake", "cmake.in"],
		filename: /^CMakeLists\.txt$/,
		load() {
			return __vitePreload(() => import("./cmake-Lo3y1mFH.js").then((m) => legacy(m.cmake)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "CoffeeScript",
		alias: ["coffee", "coffee-script"],
		extensions: ["coffee"],
		load() {
			return __vitePreload(() => import("./coffeescript-B-rGnLax.js").then((m) => legacy(m.coffeeScript)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Common Lisp",
		alias: ["lisp"],
		extensions: [
			"cl",
			"lisp",
			"el"
		],
		load() {
			return __vitePreload(() => import("./commonlisp-DP-wtNlG.js").then((m) => legacy(m.commonLisp)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Cypher",
		extensions: ["cyp", "cypher"],
		load() {
			return __vitePreload(() => import("./cypher-BEU1GtlE.js").then((m) => legacy(m.cypher)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Cython",
		extensions: [
			"pyx",
			"pxd",
			"pxi"
		],
		load() {
			return __vitePreload(() => import("./python-C7erxXjz.js").then((m) => legacy(m.cython)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Crystal",
		extensions: ["cr"],
		load() {
			return __vitePreload(() => import("./crystal-DxjpwdIq.js").then((m) => legacy(m.crystal)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "D",
		extensions: ["d"],
		load() {
			return __vitePreload(() => import("./d-CFrSru0v.js").then((m) => legacy(m.d)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Dart",
		extensions: ["dart"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.dart)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "diff",
		extensions: ["diff", "patch"],
		load() {
			return __vitePreload(() => import("./diff-CECVVGXO.js").then((m) => legacy(m.diff)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Dockerfile",
		filename: /^Dockerfile$/,
		load() {
			return __vitePreload(() => import("./dockerfile-BKceAHtN.js").then((m) => legacy(m.dockerFile)), __vite__mapDeps([23,24]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "DTD",
		extensions: ["dtd"],
		load() {
			return __vitePreload(() => import("./dtd-VXkCpieh.js").then((m) => legacy(m.dtd)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Dylan",
		extensions: [
			"dylan",
			"dyl",
			"intr"
		],
		load() {
			return __vitePreload(() => import("./dylan-UypkpUuU.js").then((m) => legacy(m.dylan)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "EBNF",
		load() {
			return __vitePreload(() => import("./ebnf-BnyAl4-I.js").then((m) => legacy(m.ebnf)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ECL",
		extensions: ["ecl"],
		load() {
			return __vitePreload(() => import("./ecl-BSMkF26o.js").then((m) => legacy(m.ecl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "edn",
		extensions: ["edn"],
		load() {
			return __vitePreload(() => import("./clojure-Cuc-6ayA.js").then((m) => legacy(m.clojure)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Eiffel",
		extensions: ["e"],
		load() {
			return __vitePreload(() => import("./eiffel-CcZREUnM.js").then((m) => legacy(m.eiffel)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Elm",
		extensions: ["elm"],
		load() {
			return __vitePreload(() => import("./elm-BYvSGZRC.js").then((m) => legacy(m.elm)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Erlang",
		extensions: ["erl"],
		load() {
			return __vitePreload(() => import("./erlang-DWMai5wi.js").then((m) => legacy(m.erlang)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Esper",
		load() {
			return __vitePreload(() => import("./sql-CNbv7MCG.js").then((m) => legacy(m.esper)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Factor",
		extensions: ["factor"],
		load() {
			return __vitePreload(() => import("./factor-CJwPu3dp.js").then((m) => legacy(m.factor)), __vite__mapDeps([25,24]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "FCL",
		load() {
			return __vitePreload(() => import("./fcl-DtW5AUCB.js").then((m) => legacy(m.fcl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Forth",
		extensions: [
			"forth",
			"fth",
			"4th"
		],
		load() {
			return __vitePreload(() => import("./forth-BfUuP-GH.js").then((m) => legacy(m.forth)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Fortran",
		extensions: [
			"f",
			"for",
			"f77",
			"f90",
			"f95"
		],
		load() {
			return __vitePreload(() => import("./fortran-BBgiKo3z.js").then((m) => legacy(m.fortran)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "F#",
		alias: ["fsharp"],
		extensions: ["fs"],
		load() {
			return __vitePreload(() => import("./mllike-DdFgMPX1.js").then((m) => legacy(m.fSharp)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Gas",
		extensions: ["s"],
		load() {
			return __vitePreload(() => import("./gas-CTNjJ4dD.js").then((m) => legacy(m.gas)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Gherkin",
		extensions: ["feature"],
		load() {
			return __vitePreload(() => import("./gherkin-DzYbEwDO.js").then((m) => legacy(m.gherkin)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Groovy",
		extensions: ["groovy", "gradle"],
		filename: /^Jenkinsfile$/,
		load() {
			return __vitePreload(() => import("./groovy-CEIupiCC.js").then((m) => legacy(m.groovy)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Haskell",
		extensions: ["hs"],
		load() {
			return __vitePreload(() => import("./haskell-2zzD22hs.js").then((m) => legacy(m.haskell)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Haxe",
		extensions: ["hx"],
		load() {
			return __vitePreload(() => import("./haxe-ypwusOXu.js").then((m) => legacy(m.haxe)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "HXML",
		extensions: ["hxml"],
		load() {
			return __vitePreload(() => import("./haxe-ypwusOXu.js").then((m) => legacy(m.hxml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "HTTP",
		load() {
			return __vitePreload(() => import("./http-BMX-u1Ja.js").then((m) => legacy(m.http)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "IDL",
		extensions: ["pro"],
		load() {
			return __vitePreload(() => import("./idl-BunNptKM.js").then((m) => legacy(m.idl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JSON-LD",
		alias: ["jsonld"],
		extensions: ["jsonld"],
		load() {
			return __vitePreload(() => import("./javascript-Bgsg0Ond.js").then((m) => legacy(m.jsonld)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Julia",
		extensions: ["jl"],
		load() {
			return __vitePreload(() => import("./julia-BtttIpfP.js").then((m) => legacy(m.julia)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Kotlin",
		extensions: ["kt", "kts"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.kotlin)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "LiveScript",
		alias: ["ls"],
		extensions: ["ls"],
		load() {
			return __vitePreload(() => import("./livescript-SBL8U_rP.js").then((m) => legacy(m.liveScript)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Lua",
		extensions: ["lua"],
		load() {
			return __vitePreload(() => import("./lua-CSj1SXeW.js").then((m) => legacy(m.lua)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "mIRC",
		extensions: ["mrc"],
		load() {
			return __vitePreload(() => import("./mirc-CFRruNsl.js").then((m) => legacy(m.mirc)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Mathematica",
		extensions: [
			"m",
			"nb",
			"wl",
			"wls"
		],
		load() {
			return __vitePreload(() => import("./mathematica-DBWAnQUB.js").then((m) => legacy(m.mathematica)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Modelica",
		extensions: ["mo"],
		load() {
			return __vitePreload(() => import("./modelica-B1Vl0iht.js").then((m) => legacy(m.modelica)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MUMPS",
		extensions: ["mps"],
		load() {
			return __vitePreload(() => import("./mumps-BDj3Mkgv.js").then((m) => legacy(m.mumps)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Mbox",
		extensions: ["mbox"],
		load() {
			return __vitePreload(() => import("./mbox-DPAEAHJ_.js").then((m) => legacy(m.mbox)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Nginx",
		filename: /nginx.*\.conf$/i,
		load() {
			return __vitePreload(() => import("./nginx-DlSaumfH.js").then((m) => legacy(m.nginx)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "NSIS",
		extensions: ["nsh", "nsi"],
		load() {
			return __vitePreload(() => import("./nsis-OBNRHa9B.js").then((m) => legacy(m.nsis)), __vite__mapDeps([26,24]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "NTriples",
		extensions: ["nt", "nq"],
		load() {
			return __vitePreload(() => import("./ntriples-Cy0EtpqS.js").then((m) => legacy(m.ntriples)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Objective-C",
		alias: ["objective-c", "objc"],
		extensions: ["m"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.objectiveC)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Objective-C++",
		alias: ["objective-c++", "objc++"],
		extensions: ["mm"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.objectiveCpp)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "OCaml",
		extensions: [
			"ml",
			"mli",
			"mll",
			"mly"
		],
		load() {
			return __vitePreload(() => import("./mllike-DdFgMPX1.js").then((m) => legacy(m.oCaml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Octave",
		extensions: ["m"],
		load() {
			return __vitePreload(() => import("./octave-Jq4lsXTP.js").then((m) => legacy(m.octave)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Oz",
		extensions: ["oz"],
		load() {
			return __vitePreload(() => import("./oz-D9XaQody.js").then((m) => legacy(m.oz)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Pascal",
		extensions: ["p", "pas"],
		load() {
			return __vitePreload(() => import("./pascal-DxTQDPq-.js").then((m) => legacy(m.pascal)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Perl",
		extensions: ["pl", "pm"],
		load() {
			return __vitePreload(() => import("./perl-BZ4GNJdA.js").then((m) => legacy(m.perl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Pig",
		extensions: ["pig"],
		load() {
			return __vitePreload(() => import("./pig-DCIZ91pY.js").then((m) => legacy(m.pig)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "PowerShell",
		extensions: [
			"ps1",
			"psd1",
			"psm1"
		],
		load() {
			return __vitePreload(() => import("./powershell-BhxeIEF6.js").then((m) => legacy(m.powerShell)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Properties files",
		alias: ["ini", "properties"],
		extensions: [
			"properties",
			"ini",
			"in"
		],
		load() {
			return __vitePreload(() => import("./properties-CkfN6_NO.js").then((m) => legacy(m.properties)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ProtoBuf",
		extensions: ["proto"],
		load() {
			return __vitePreload(() => import("./protobuf-FD46u9Te.js").then((m) => legacy(m.protobuf)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Pug",
		alias: ["jade"],
		extensions: ["pug", "jade"],
		load() {
			return __vitePreload(() => import("./pug-BOEIvkN-.js").then((m) => legacy(m.pug)), __vite__mapDeps([27,28]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Puppet",
		extensions: ["pp"],
		load() {
			return __vitePreload(() => import("./puppet-CrJU0wXt.js").then((m) => legacy(m.puppet)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Q",
		extensions: ["q"],
		load() {
			return __vitePreload(() => import("./q-2y-OI7Gq.js").then((m) => legacy(m.q)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "R",
		alias: ["rscript"],
		extensions: ["r", "R"],
		load() {
			return __vitePreload(() => import("./r-BJOMcSw0.js").then((m) => legacy(m.r)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "RPM Changes",
		load() {
			return __vitePreload(() => import("./rpm-CzqdVT2t.js").then((m) => legacy(m.rpmChanges)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "RPM Spec",
		extensions: ["spec"],
		load() {
			return __vitePreload(() => import("./rpm-CzqdVT2t.js").then((m) => legacy(m.rpmSpec)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Ruby",
		alias: [
			"jruby",
			"macruby",
			"rake",
			"rb",
			"rbx"
		],
		extensions: ["rb"],
		filename: /^(Gemfile|Rakefile)$/,
		load() {
			return __vitePreload(() => import("./ruby-BCRtCS1T.js").then((m) => legacy(m.ruby)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SAS",
		extensions: ["sas"],
		load() {
			return __vitePreload(() => import("./sas-BYaDQw_a.js").then((m) => legacy(m.sas)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Scala",
		extensions: ["scala"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.scala)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Scheme",
		extensions: ["scm", "ss"],
		load() {
			return __vitePreload(() => import("./scheme-BtAqJJQN.js").then((m) => legacy(m.scheme)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Shell",
		alias: [
			"bash",
			"sh",
			"zsh"
		],
		extensions: [
			"sh",
			"ksh",
			"bash"
		],
		filename: /^PKGBUILD$/,
		load() {
			return __vitePreload(() => import("./shell-Dh5IwHd-.js").then((m) => legacy(m.shell)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Sieve",
		extensions: ["siv", "sieve"],
		load() {
			return __vitePreload(() => import("./sieve-6sorq5_v.js").then((m) => legacy(m.sieve)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Smalltalk",
		extensions: ["st"],
		load() {
			return __vitePreload(() => import("./smalltalk-DOYRz-oa.js").then((m) => legacy(m.smalltalk)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Solr",
		load() {
			return __vitePreload(() => import("./solr-CupUnHh5.js").then((m) => legacy(m.solr)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SML",
		extensions: [
			"sml",
			"sig",
			"fun",
			"smackspec"
		],
		load() {
			return __vitePreload(() => import("./mllike-DdFgMPX1.js").then((m) => legacy(m.sml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SPARQL",
		alias: ["sparul"],
		extensions: ["rq", "sparql"],
		load() {
			return __vitePreload(() => import("./sparql-B1tA_iK1.js").then((m) => legacy(m.sparql)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Spreadsheet",
		alias: ["excel", "formula"],
		load() {
			return __vitePreload(() => import("./spreadsheet-0dwepZJJ.js").then((m) => legacy(m.spreadsheet)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Squirrel",
		extensions: ["nut"],
		load() {
			return __vitePreload(() => import("./clike-Cn_BXDUY.js").then((m) => legacy(m.squirrel)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Stylus",
		extensions: ["styl"],
		load() {
			return __vitePreload(() => import("./stylus-B9KnClte.js").then((m) => legacy(m.stylus)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Swift",
		extensions: ["swift"],
		load() {
			return __vitePreload(() => import("./swift-BeQXoCoc.js").then((m) => legacy(m.swift)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "sTeX",
		load() {
			return __vitePreload(() => import("./stex-BMkoU5jO.js").then((m) => legacy(m.stex)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "LaTeX",
		alias: ["tex"],
		extensions: [
			"text",
			"ltx",
			"tex"
		],
		load() {
			return __vitePreload(() => import("./stex-BMkoU5jO.js").then((m) => legacy(m.stex)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SystemVerilog",
		extensions: [
			"v",
			"sv",
			"svh"
		],
		load() {
			return __vitePreload(() => import("./verilog-Bl8g08YK.js").then((m) => legacy(m.verilog)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Tcl",
		extensions: ["tcl"],
		load() {
			return __vitePreload(() => import("./tcl-CcviB-6J.js").then((m) => legacy(m.tcl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Textile",
		extensions: ["textile"],
		load() {
			return __vitePreload(() => import("./textile-DLXezbFx.js").then((m) => legacy(m.textile)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TiddlyWiki",
		load() {
			return __vitePreload(() => import("./tiddlywiki-JSG3uedW.js").then((m) => legacy(m.tiddlyWiki)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Tiki wiki",
		load() {
			return __vitePreload(() => import("./tiki-Dub_RbnZ.js").then((m) => legacy(m.tiki)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TOML",
		extensions: ["toml"],
		load() {
			return __vitePreload(() => import("./toml-D0Pix_8Q.js").then((m) => legacy(m.toml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Troff",
		extensions: [
			"1",
			"2",
			"3",
			"4",
			"5",
			"6",
			"7",
			"8",
			"9"
		],
		load() {
			return __vitePreload(() => import("./troff-C4-NwjFV.js").then((m) => legacy(m.troff)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TTCN",
		extensions: [
			"ttcn",
			"ttcn3",
			"ttcnpp"
		],
		load() {
			return __vitePreload(() => import("./ttcn-CUGaQbxi.js").then((m) => legacy(m.ttcn)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TTCN_CFG",
		extensions: ["cfg"],
		load() {
			return __vitePreload(() => import("./ttcn-cfg-D6RTxK-C.js").then((m) => legacy(m.ttcnCfg)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Turtle",
		extensions: ["ttl"],
		load() {
			return __vitePreload(() => import("./turtle-ByxHuOOQ.js").then((m) => legacy(m.turtle)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Web IDL",
		extensions: ["webidl"],
		load() {
			return __vitePreload(() => import("./webidl-DMdzwo0j.js").then((m) => legacy(m.webIDL)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "VB.NET",
		extensions: ["vb"],
		load() {
			return __vitePreload(() => import("./vb-Pk8l8i6z.js").then((m) => legacy(m.vb)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "VBScript",
		extensions: ["vbs"],
		load() {
			return __vitePreload(() => import("./vbscript-BdzlvW_o.js").then((m) => legacy(m.vbScript)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Velocity",
		extensions: ["vtl"],
		load() {
			return __vitePreload(() => import("./velocity-CAOFwxxP.js").then((m) => legacy(m.velocity)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Verilog",
		extensions: ["v"],
		load() {
			return __vitePreload(() => import("./verilog-Bl8g08YK.js").then((m) => legacy(m.verilog)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "VHDL",
		extensions: ["vhd", "vhdl"],
		load() {
			return __vitePreload(() => import("./vhdl-B96B6aiO.js").then((m) => legacy(m.vhdl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "XQuery",
		extensions: [
			"xy",
			"xquery",
			"xq",
			"xqm",
			"xqy"
		],
		load() {
			return __vitePreload(() => import("./xquery-9wH1oKXV.js").then((m) => legacy(m.xQuery)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Yacas",
		extensions: ["ys"],
		load() {
			return __vitePreload(() => import("./yacas-CI_uZ86a.js").then((m) => legacy(m.yacas)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Z80",
		extensions: ["z80"],
		load() {
			return __vitePreload(() => import("./z80-ByAXzAIF.js").then((m) => legacy(m.z80)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MscGen",
		extensions: [
			"mscgen",
			"mscin",
			"msc"
		],
		load() {
			return __vitePreload(() => import("./mscgen-DE7ddYo_.js").then((m) => legacy(m.mscgen)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Xù",
		extensions: ["xu"],
		load() {
			return __vitePreload(() => import("./mscgen-DE7ddYo_.js").then((m) => legacy(m.xu)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MsGenny",
		extensions: ["msgenny"],
		load() {
			return __vitePreload(() => import("./mscgen-DE7ddYo_.js").then((m) => legacy(m.msgenny)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Vue",
		extensions: ["vue"],
		load() {
			return __vitePreload(() => import("./dist-B_LqJYNN.js").then((m) => m.vue()), __vite__mapDeps([29,1,2,8,3,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Angular Template",
		load() {
			return __vitePreload(() => import("./dist-gubZSbzE.js").then((m) => m.angular()), __vite__mapDeps([30,1,2,8,3,6,9,4]));
		}
	})
];
export { languages };
