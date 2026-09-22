const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/dist-ByPMn19-.js","assets/dist-CFtxRP70.js","assets/dist-CzEUVXDC.js","assets/dist-Dp7zcg8q.js","assets/dist-n09HnSQH.js","assets/dist-CtgMfojb.js","assets/dist-CWt5MqEz.js","assets/dist-BCDxotJ1.js","assets/dist-BtjFFX5g.js","assets/dist-D8zCp1Lk.js","assets/dist-CYliqEuh.js","assets/dist-DOjPMnBQ.js","assets/dist-au17DMQY.js","assets/dist-B2J_1-Na.js","assets/dist-DwDnwnlH.js","assets/dist-CtvrPQL3.js","assets/dist-q1OvipzT.js","assets/dist-BLURfKbJ.js","assets/dist-CgAoKeyx.js","assets/dist-B1nGpcQK.js","assets/dist-jFV8Q6Ck.js","assets/dist-CvCpFeRI.js","assets/dist-Bj2N8gQv.js","assets/dockerfile-CIE65g0n.js","assets/simple-mode-BApxjfXS.js","assets/factor-BKz8VQZ5.js","assets/nsis-Bcd8y5Bg.js","assets/pug-DXvAcW6A.js","assets/javascript-vc8XVW5V.js","assets/dist-BpX2EKOq.js","assets/dist-BrlS-zD6.js"])))=>i.map(i=>d[i]);
import { t as __vitePreload } from "./index-CVOeYyHe.js";
import { LanguageDescription, LanguageSupport, StreamLanguage } from "./dist-CFtxRP70.js";
//#region node_modules/@codemirror/language-data/dist/index.js
function legacy(parser) {
	return new LanguageSupport(StreamLanguage.define(parser));
}
function sql(dialectName) {
	return __vitePreload(() => import("./dist-ByPMn19-.js").then((m) => m.sql({ dialect: m[dialectName] })), __vite__mapDeps([0,1,2,3,4]));
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
			return __vitePreload(() => import("./dist-CtgMfojb.js").then((m) => m.cpp()), __vite__mapDeps([5,1,2,3]));
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
			return __vitePreload(() => import("./dist-CtgMfojb.js").then((m) => m.cpp()), __vite__mapDeps([5,1,2,3]));
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
			return __vitePreload(() => import("./dist-CWt5MqEz.js").then((n) => n.i).then((m) => m.css()), __vite__mapDeps([6,2,1,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Go",
		extensions: ["go"],
		load() {
			return __vitePreload(() => import("./dist-BCDxotJ1.js").then((m) => m.go()), __vite__mapDeps([7,1,2,3,4]));
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
			return __vitePreload(() => import("./dist-BtjFFX5g.js").then((m) => m.html()), __vite__mapDeps([8,2,1,3,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Java",
		extensions: ["java"],
		load() {
			return __vitePreload(() => import("./dist-CYliqEuh.js").then((m) => m.java()), __vite__mapDeps([10,1,2,3]));
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
			return __vitePreload(() => import("./dist-D8zCp1Lk.js").then((n) => n.t).then((m) => m.javascript()), __vite__mapDeps([9,2,1,3,4]));
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
			return __vitePreload(() => import("./dist-DOjPMnBQ.js").then((m) => m.jinja()), __vite__mapDeps([11,2,1,3,8,6,9,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JSON",
		alias: ["json5"],
		extensions: ["json", "map"],
		load() {
			return __vitePreload(() => import("./dist-au17DMQY.js").then((m) => m.json()), __vite__mapDeps([12,1,2,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JSX",
		extensions: ["jsx"],
		load() {
			return __vitePreload(() => import("./dist-D8zCp1Lk.js").then((n) => n.t).then((m) => m.javascript({ jsx: true })), __vite__mapDeps([9,2,1,3,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "LESS",
		extensions: ["less"],
		load() {
			return __vitePreload(() => import("./dist-B2J_1-Na.js").then((m) => m.less()), __vite__mapDeps([13,1,2,3,6]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Liquid",
		extensions: ["liquid"],
		load() {
			return __vitePreload(() => import("./dist-DwDnwnlH.js").then((m) => m.liquid()), __vite__mapDeps([14,2,1,3,8,6,9,4]));
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
			return __vitePreload(() => import("./dist-CtvrPQL3.js").then((m) => m.markdown()), __vite__mapDeps([15,2,1,4,8,3,6,9]));
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
			return __vitePreload(() => import("./dist-q1OvipzT.js").then((m) => m.php()), __vite__mapDeps([16,1,2,3,8,6,9,4]));
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
			return __vitePreload(() => import("./dist-BLURfKbJ.js").then((m) => m.python()), __vite__mapDeps([17,1,2,3,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Rust",
		extensions: ["rs"],
		load() {
			return __vitePreload(() => import("./dist-CgAoKeyx.js").then((m) => m.rust()), __vite__mapDeps([18,1,2,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Sass",
		extensions: ["sass"],
		load() {
			return __vitePreload(() => import("./dist-B1nGpcQK.js").then((m) => m.sass({ indented: true })), __vite__mapDeps([19,1,2,3,6]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SCSS",
		extensions: ["scss"],
		load() {
			return __vitePreload(() => import("./dist-B1nGpcQK.js").then((m) => m.sass()), __vite__mapDeps([19,1,2,3,6]));
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
			return __vitePreload(() => import("./dist-D8zCp1Lk.js").then((n) => n.t).then((m) => m.javascript({
				jsx: true,
				typescript: true
			})), __vite__mapDeps([9,2,1,3,4]));
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
			return __vitePreload(() => import("./dist-D8zCp1Lk.js").then((n) => n.t).then((m) => m.javascript({ typescript: true })), __vite__mapDeps([9,2,1,3,4]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "WebAssembly",
		extensions: ["wat", "wast"],
		load() {
			return __vitePreload(() => import("./dist-jFV8Q6Ck.js").then((m) => m.wast()), __vite__mapDeps([20,1,2,3]));
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
			return __vitePreload(() => import("./dist-CvCpFeRI.js").then((m) => m.xml()), __vite__mapDeps([21,2,1,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "YAML",
		alias: ["yml"],
		extensions: ["yaml", "yml"],
		load() {
			return __vitePreload(() => import("./dist-Bj2N8gQv.js").then((m) => m.yaml()), __vite__mapDeps([22,1,2,3]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "APL",
		extensions: ["dyalog", "apl"],
		load() {
			return __vitePreload(() => import("./apl-3JbH1QFw.js").then((m) => legacy(m.apl)), []);
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
			return __vitePreload(() => import("./asciiarmor-DlF9oBYN.js").then((m) => legacy(m.asciiArmor)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ASN.1",
		extensions: ["asn", "asn1"],
		load() {
			return __vitePreload(() => import("./asn1-CmMlHCrA.js").then((m) => legacy(m.asn1({}))), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Asterisk",
		filename: /^extensions\.conf$/i,
		load() {
			return __vitePreload(() => import("./asterisk-B_SzUelr.js").then((m) => legacy(m.asterisk)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Brainfuck",
		extensions: ["b", "bf"],
		load() {
			return __vitePreload(() => import("./brainfuck-uPmJfZWY.js").then((m) => legacy(m.brainfuck)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Cobol",
		extensions: ["cob", "cpy"],
		load() {
			return __vitePreload(() => import("./cobol-_miRv5C1.js").then((m) => legacy(m.cobol)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "C#",
		alias: ["csharp", "cs"],
		extensions: ["cs"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.csharp)), []);
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
			return __vitePreload(() => import("./clojure-CaJQmIml.js").then((m) => legacy(m.clojure)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ClojureScript",
		extensions: ["cljs"],
		load() {
			return __vitePreload(() => import("./clojure-CaJQmIml.js").then((m) => legacy(m.clojure)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Closure Stylesheets (GSS)",
		extensions: ["gss"],
		load() {
			return __vitePreload(() => import("./css-BHQMnn8O.js").then((m) => legacy(m.gss)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "CMake",
		extensions: ["cmake", "cmake.in"],
		filename: /^CMakeLists\.txt$/,
		load() {
			return __vitePreload(() => import("./cmake-DFbHdH-1.js").then((m) => legacy(m.cmake)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "CoffeeScript",
		alias: ["coffee", "coffee-script"],
		extensions: ["coffee"],
		load() {
			return __vitePreload(() => import("./coffeescript-DvbdwHer.js").then((m) => legacy(m.coffeeScript)), []);
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
			return __vitePreload(() => import("./commonlisp-T4OUvQcc.js").then((m) => legacy(m.commonLisp)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Cypher",
		extensions: ["cyp", "cypher"],
		load() {
			return __vitePreload(() => import("./cypher-CblJrMBc.js").then((m) => legacy(m.cypher)), []);
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
			return __vitePreload(() => import("./python-BKpCL89U.js").then((m) => legacy(m.cython)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Crystal",
		extensions: ["cr"],
		load() {
			return __vitePreload(() => import("./crystal-DHjYP0rj.js").then((m) => legacy(m.crystal)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "D",
		extensions: ["d"],
		load() {
			return __vitePreload(() => import("./d-Sy730XLP.js").then((m) => legacy(m.d)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Dart",
		extensions: ["dart"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.dart)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "diff",
		extensions: ["diff", "patch"],
		load() {
			return __vitePreload(() => import("./diff-ei2LzbNV.js").then((m) => legacy(m.diff)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Dockerfile",
		filename: /^Dockerfile$/,
		load() {
			return __vitePreload(() => import("./dockerfile-CIE65g0n.js").then((m) => legacy(m.dockerFile)), __vite__mapDeps([23,24]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "DTD",
		extensions: ["dtd"],
		load() {
			return __vitePreload(() => import("./dtd-CbNqZR6-.js").then((m) => legacy(m.dtd)), []);
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
			return __vitePreload(() => import("./dylan-BFdNtKBD.js").then((m) => legacy(m.dylan)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "EBNF",
		load() {
			return __vitePreload(() => import("./ebnf-CyPZmPnq.js").then((m) => legacy(m.ebnf)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ECL",
		extensions: ["ecl"],
		load() {
			return __vitePreload(() => import("./ecl-hMyS5s6r.js").then((m) => legacy(m.ecl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "edn",
		extensions: ["edn"],
		load() {
			return __vitePreload(() => import("./clojure-CaJQmIml.js").then((m) => legacy(m.clojure)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Eiffel",
		extensions: ["e"],
		load() {
			return __vitePreload(() => import("./eiffel-B9pxPixJ.js").then((m) => legacy(m.eiffel)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Elm",
		extensions: ["elm"],
		load() {
			return __vitePreload(() => import("./elm-DE2kDZmp.js").then((m) => legacy(m.elm)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Erlang",
		extensions: ["erl"],
		load() {
			return __vitePreload(() => import("./erlang-z945da73.js").then((m) => legacy(m.erlang)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Esper",
		load() {
			return __vitePreload(() => import("./sql-D9nEMNhz.js").then((m) => legacy(m.esper)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Factor",
		extensions: ["factor"],
		load() {
			return __vitePreload(() => import("./factor-BKz8VQZ5.js").then((m) => legacy(m.factor)), __vite__mapDeps([25,24]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "FCL",
		load() {
			return __vitePreload(() => import("./fcl-U9HGYJzK.js").then((m) => legacy(m.fcl)), []);
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
			return __vitePreload(() => import("./forth-Cmn9JVoA.js").then((m) => legacy(m.forth)), []);
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
			return __vitePreload(() => import("./fortran-BOtmusLb.js").then((m) => legacy(m.fortran)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "F#",
		alias: ["fsharp"],
		extensions: ["fs"],
		load() {
			return __vitePreload(() => import("./mllike-CmByegCz.js").then((m) => legacy(m.fSharp)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Gas",
		extensions: ["s"],
		load() {
			return __vitePreload(() => import("./gas-J1t9Zg0-.js").then((m) => legacy(m.gas)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Gherkin",
		extensions: ["feature"],
		load() {
			return __vitePreload(() => import("./gherkin-uCVRxsGf.js").then((m) => legacy(m.gherkin)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Groovy",
		extensions: ["groovy", "gradle"],
		filename: /^Jenkinsfile$/,
		load() {
			return __vitePreload(() => import("./groovy-D9efc7JA.js").then((m) => legacy(m.groovy)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Haskell",
		extensions: ["hs"],
		load() {
			return __vitePreload(() => import("./haskell-CuQ2KxRY.js").then((m) => legacy(m.haskell)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Haxe",
		extensions: ["hx"],
		load() {
			return __vitePreload(() => import("./haxe-CqdEYr-s.js").then((m) => legacy(m.haxe)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "HXML",
		extensions: ["hxml"],
		load() {
			return __vitePreload(() => import("./haxe-CqdEYr-s.js").then((m) => legacy(m.hxml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "HTTP",
		load() {
			return __vitePreload(() => import("./http-DYyYgr7m.js").then((m) => legacy(m.http)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "IDL",
		extensions: ["pro"],
		load() {
			return __vitePreload(() => import("./idl-CdIKZnKf.js").then((m) => legacy(m.idl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "JSON-LD",
		alias: ["jsonld"],
		extensions: ["jsonld"],
		load() {
			return __vitePreload(() => import("./javascript-vc8XVW5V.js").then((m) => legacy(m.jsonld)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Julia",
		extensions: ["jl"],
		load() {
			return __vitePreload(() => import("./julia-DZM201TO.js").then((m) => legacy(m.julia)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Kotlin",
		extensions: ["kt", "kts"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.kotlin)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "LiveScript",
		alias: ["ls"],
		extensions: ["ls"],
		load() {
			return __vitePreload(() => import("./livescript-Ej6amSYl.js").then((m) => legacy(m.liveScript)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Lua",
		extensions: ["lua"],
		load() {
			return __vitePreload(() => import("./lua-CCSUdSHz.js").then((m) => legacy(m.lua)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "mIRC",
		extensions: ["mrc"],
		load() {
			return __vitePreload(() => import("./mirc-0u3GVQND.js").then((m) => legacy(m.mirc)), []);
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
			return __vitePreload(() => import("./mathematica-BO4dqqp2.js").then((m) => legacy(m.mathematica)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Modelica",
		extensions: ["mo"],
		load() {
			return __vitePreload(() => import("./modelica-Cm0D7UOA.js").then((m) => legacy(m.modelica)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MUMPS",
		extensions: ["mps"],
		load() {
			return __vitePreload(() => import("./mumps-DGogVbYh.js").then((m) => legacy(m.mumps)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Mbox",
		extensions: ["mbox"],
		load() {
			return __vitePreload(() => import("./mbox-C1De1rCN.js").then((m) => legacy(m.mbox)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Nginx",
		filename: /nginx.*\.conf$/i,
		load() {
			return __vitePreload(() => import("./nginx-Dh0fb_np.js").then((m) => legacy(m.nginx)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "NSIS",
		extensions: ["nsh", "nsi"],
		load() {
			return __vitePreload(() => import("./nsis-Bcd8y5Bg.js").then((m) => legacy(m.nsis)), __vite__mapDeps([26,24]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "NTriples",
		extensions: ["nt", "nq"],
		load() {
			return __vitePreload(() => import("./ntriples-BtZY9Tg2.js").then((m) => legacy(m.ntriples)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Objective-C",
		alias: ["objective-c", "objc"],
		extensions: ["m"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.objectiveC)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Objective-C++",
		alias: ["objective-c++", "objc++"],
		extensions: ["mm"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.objectiveCpp)), []);
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
			return __vitePreload(() => import("./mllike-CmByegCz.js").then((m) => legacy(m.oCaml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Octave",
		extensions: ["m"],
		load() {
			return __vitePreload(() => import("./octave-D-Mf_lP5.js").then((m) => legacy(m.octave)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Oz",
		extensions: ["oz"],
		load() {
			return __vitePreload(() => import("./oz-BzzQuVjw.js").then((m) => legacy(m.oz)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Pascal",
		extensions: ["p", "pas"],
		load() {
			return __vitePreload(() => import("./pascal-ftTHxfIF.js").then((m) => legacy(m.pascal)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Perl",
		extensions: ["pl", "pm"],
		load() {
			return __vitePreload(() => import("./perl-DikKQqid.js").then((m) => legacy(m.perl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Pig",
		extensions: ["pig"],
		load() {
			return __vitePreload(() => import("./pig-CIYd1dzp.js").then((m) => legacy(m.pig)), []);
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
			return __vitePreload(() => import("./powershell-BYm6PeTI.js").then((m) => legacy(m.powerShell)), []);
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
			return __vitePreload(() => import("./properties-BLRsJH4R.js").then((m) => legacy(m.properties)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "ProtoBuf",
		extensions: ["proto"],
		load() {
			return __vitePreload(() => import("./protobuf-B1tneDx6.js").then((m) => legacy(m.protobuf)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Pug",
		alias: ["jade"],
		extensions: ["pug", "jade"],
		load() {
			return __vitePreload(() => import("./pug-DXvAcW6A.js").then((m) => legacy(m.pug)), __vite__mapDeps([27,28]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Puppet",
		extensions: ["pp"],
		load() {
			return __vitePreload(() => import("./puppet-CgjfFbLI.js").then((m) => legacy(m.puppet)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Q",
		extensions: ["q"],
		load() {
			return __vitePreload(() => import("./q-DycYsP7S.js").then((m) => legacy(m.q)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "R",
		alias: ["rscript"],
		extensions: ["r", "R"],
		load() {
			return __vitePreload(() => import("./r-C94J1haf.js").then((m) => legacy(m.r)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "RPM Changes",
		load() {
			return __vitePreload(() => import("./rpm-C7__opOD.js").then((m) => legacy(m.rpmChanges)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "RPM Spec",
		extensions: ["spec"],
		load() {
			return __vitePreload(() => import("./rpm-C7__opOD.js").then((m) => legacy(m.rpmSpec)), []);
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
			return __vitePreload(() => import("./ruby-Dom_v4Iq.js").then((m) => legacy(m.ruby)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SAS",
		extensions: ["sas"],
		load() {
			return __vitePreload(() => import("./sas-BvudxRYJ.js").then((m) => legacy(m.sas)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Scala",
		extensions: ["scala"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.scala)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Scheme",
		extensions: ["scm", "ss"],
		load() {
			return __vitePreload(() => import("./scheme-BxtBrD3J.js").then((m) => legacy(m.scheme)), []);
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
			return __vitePreload(() => import("./shell-C61GCsJA.js").then((m) => legacy(m.shell)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Sieve",
		extensions: ["siv", "sieve"],
		load() {
			return __vitePreload(() => import("./sieve-uP63Glg0.js").then((m) => legacy(m.sieve)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Smalltalk",
		extensions: ["st"],
		load() {
			return __vitePreload(() => import("./smalltalk-DdwwK_SA.js").then((m) => legacy(m.smalltalk)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Solr",
		load() {
			return __vitePreload(() => import("./solr-CWIKYH15.js").then((m) => legacy(m.solr)), []);
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
			return __vitePreload(() => import("./mllike-CmByegCz.js").then((m) => legacy(m.sml)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "SPARQL",
		alias: ["sparul"],
		extensions: ["rq", "sparql"],
		load() {
			return __vitePreload(() => import("./sparql-D_IkwgoY.js").then((m) => legacy(m.sparql)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Spreadsheet",
		alias: ["excel", "formula"],
		load() {
			return __vitePreload(() => import("./spreadsheet-BRJxPl_W.js").then((m) => legacy(m.spreadsheet)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Squirrel",
		extensions: ["nut"],
		load() {
			return __vitePreload(() => import("./clike-C5rEHood.js").then((m) => legacy(m.squirrel)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Stylus",
		extensions: ["styl"],
		load() {
			return __vitePreload(() => import("./stylus-hik8gpcV.js").then((m) => legacy(m.stylus)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Swift",
		extensions: ["swift"],
		load() {
			return __vitePreload(() => import("./swift-G96yl6qt.js").then((m) => legacy(m.swift)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "sTeX",
		load() {
			return __vitePreload(() => import("./stex-BUlOgYBB.js").then((m) => legacy(m.stex)), []);
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
			return __vitePreload(() => import("./stex-BUlOgYBB.js").then((m) => legacy(m.stex)), []);
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
			return __vitePreload(() => import("./verilog-CBTlj_zR.js").then((m) => legacy(m.verilog)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Tcl",
		extensions: ["tcl"],
		load() {
			return __vitePreload(() => import("./tcl-C6Dlqr9m.js").then((m) => legacy(m.tcl)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Textile",
		extensions: ["textile"],
		load() {
			return __vitePreload(() => import("./textile-DyqB1XHS.js").then((m) => legacy(m.textile)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TiddlyWiki",
		load() {
			return __vitePreload(() => import("./tiddlywiki-DAG3lyqI.js").then((m) => legacy(m.tiddlyWiki)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Tiki wiki",
		load() {
			return __vitePreload(() => import("./tiki-CN2gc5yH.js").then((m) => legacy(m.tiki)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TOML",
		extensions: ["toml"],
		load() {
			return __vitePreload(() => import("./toml-C2HBbPgG.js").then((m) => legacy(m.toml)), []);
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
			return __vitePreload(() => import("./troff-DpKX83PR.js").then((m) => legacy(m.troff)), []);
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
			return __vitePreload(() => import("./ttcn-CczTlaRU.js").then((m) => legacy(m.ttcn)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "TTCN_CFG",
		extensions: ["cfg"],
		load() {
			return __vitePreload(() => import("./ttcn-cfg-M6zK9Wq3.js").then((m) => legacy(m.ttcnCfg)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Turtle",
		extensions: ["ttl"],
		load() {
			return __vitePreload(() => import("./turtle-q4p8mJR3.js").then((m) => legacy(m.turtle)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Web IDL",
		extensions: ["webidl"],
		load() {
			return __vitePreload(() => import("./webidl-CHe8-upe.js").then((m) => legacy(m.webIDL)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "VB.NET",
		extensions: ["vb"],
		load() {
			return __vitePreload(() => import("./vb-B9IXmsBX.js").then((m) => legacy(m.vb)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "VBScript",
		extensions: ["vbs"],
		load() {
			return __vitePreload(() => import("./vbscript-BhryH_5L.js").then((m) => legacy(m.vbScript)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Velocity",
		extensions: ["vtl"],
		load() {
			return __vitePreload(() => import("./velocity-DPleXteh.js").then((m) => legacy(m.velocity)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Verilog",
		extensions: ["v"],
		load() {
			return __vitePreload(() => import("./verilog-CBTlj_zR.js").then((m) => legacy(m.verilog)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "VHDL",
		extensions: ["vhd", "vhdl"],
		load() {
			return __vitePreload(() => import("./vhdl-LF6AMmOb.js").then((m) => legacy(m.vhdl)), []);
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
			return __vitePreload(() => import("./xquery-DpaEZJdC.js").then((m) => legacy(m.xQuery)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Yacas",
		extensions: ["ys"],
		load() {
			return __vitePreload(() => import("./yacas-COQeIpg9.js").then((m) => legacy(m.yacas)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Z80",
		extensions: ["z80"],
		load() {
			return __vitePreload(() => import("./z80-F_b1IDZ2.js").then((m) => legacy(m.z80)), []);
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
			return __vitePreload(() => import("./mscgen-9KnR5gwG.js").then((m) => legacy(m.mscgen)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Xù",
		extensions: ["xu"],
		load() {
			return __vitePreload(() => import("./mscgen-9KnR5gwG.js").then((m) => legacy(m.xu)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "MsGenny",
		extensions: ["msgenny"],
		load() {
			return __vitePreload(() => import("./mscgen-9KnR5gwG.js").then((m) => legacy(m.msgenny)), []);
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Vue",
		extensions: ["vue"],
		load() {
			return __vitePreload(() => import("./dist-BpX2EKOq.js").then((m) => m.vue()), __vite__mapDeps([29,1,2,3,9,4,8,6]));
		}
	}),
	/*@__PURE__*/ LanguageDescription.of({
		name: "Angular Template",
		load() {
			return __vitePreload(() => import("./dist-BrlS-zD6.js").then((m) => m.angular()), __vite__mapDeps([30,1,2,3,9,4,8,6]));
		}
	})
];
//#endregion
export { languages };
