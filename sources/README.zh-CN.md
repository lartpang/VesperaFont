# 原始基础数据

[English](README.md) | 简体中文

此目录保存构建所需的全部原始数据，全部是文本：

- `texgyrepagella-regular.txt`：**TeX Gyre Pagella Regular 2.501** 的文本源文件，正体字形轮廓与布局表的来源；
- `texgyrepagella-italic.txt`：**TeX Gyre Pagella Italic 2.501** 的文本源文件，书写体斜体的来源；
- `spacing/TeXGyrePagellaX-*.json.gz`：从 newpx 宏包附带的 **TeX Gyre Pagella X** Regular、Italic、Bold、BoldItalic（Michael Sharpe 对 Pagella 的扩展，取自 TeX Live 2026）提取的**间距参数**：每个字形的名称、字宽与墨迹外框，Unicode 映射，以及字偶距。

## 文本源文件

每份字体一个 UTF-8 文本文件（格式定义见 `fontviber/source.py`），依次包含：

- 文件头 `fontviber-source 1`，以及转换来源的文件名和 SHA-256（`from …`）；
- `info` 行：字族名、单位、上下伸、x 高度、大写高度、倾斜角，以及原作的版权、商标、设计者和许可信息（值为 JSON）；
- 每个字形一段，按字形顺序排列（变音符定位按字形序号引用，顺序必须保持）：`glyph` 字形名、`advance` 字宽、`unicode` 码位，以及轮廓命令 `M x y`（起点）、`L x y`（直线）、`C x1 y1 x2 y2 x y`（三次曲线）、`Z`（闭合），单位为字体单位，y 轴向上；
- 末尾是构建原样沿用的 8 张 OpenType 表（GDEF、GPOS、GSUB、OS/2、head、hhea、maxp、post），以十六进制保存。连字、变音符定位等规则若要写成可读的 `.fea` 文本，需要特性编译器才能重新生成，本项目只用标准库，因此保留原表。

```text
glyph A
advance 778
unicode 0041
M 15 -3
C 51 -1 88 0 124 0
…
Z
```

两份文本源由原 OTF 转换而来（`texgyrepagella-regular.otf` SHA-256 `44e64260716d8f2bbe412baa1ee99b7c995190ac4573177c24def0b9200438c7`，`texgyrepagella-italic.otf` SHA-256 `069bb27f48eb98a741715227fc6e4b7baf3639c29fc13925f70d1ed8884ac29a`，均取自 TeX Live 2026）。转换后会读回比对每个字形和每张表，从文本源构建的字体与从原 OTF 构建的字体逐字节相同；同一字体总是转换出字节相同的文件。需要重新转换时：

```bash
python3 build.py source --font /usr/local/texlive/2026/texmf-dist/fonts/opentype/public/tex-gyre/texgyrepagella-regular.otf --output sources/texgyrepagella-regular.txt
```

需要在 FontForge、Glyphs、RoboFont 等字体编辑器中查看时，可以导出为 UFO 3（输出路径以 `.ufo` 结尾；UFO 也能用同一命令转换回文本源）：

```bash
python3 build.py source --font sources/texgyrepagella-regular.txt --output texgyrepagella-regular.ufo
```

## 间距参数

间距参数文件是 gzip 压缩的 JSON（`gunzip -c` 即可阅读），每个文件记录了提取来源字体的文件名与 SHA-256。需要更换或更新间距参照时，用 Pagella X 字体重新提取：

```bash
python3 build.py spacing --font TeXGyrePagellaX-Regular.otf --output sources/spacing/TeXGyrePagellaX-Regular.json.gz
```

同一字体总是得到字节相同的文件。重新转换或提取后，需同步更新 `configs/*.json` 中对应的 `*_sha256`。

摘要：

```text
ff8920a7d55f525a94ff02e4f35d847c1be059459a27c9e90be94769586e6483  texgyrepagella-regular.txt
f3a512dfc5f7ac886239c1b6e6664627cafe423807556fa5b9f5264531629070  texgyrepagella-italic.txt
f72c17473f1a8b3b5f7b5dc274f850bbb1aeb60d249112707570394c781470b1  spacing/TeXGyrePagellaX-Regular.json.gz
e246c62eafa1f285ec621e49d317d0304329878d942c6d08d3cb88bd1dc5f60b  spacing/TeXGyrePagellaX-Italic.json.gz
cab2e03efe1170d431be85a90e556d2d9355614957629161294dd970bfaaf957  spacing/TeXGyrePagellaX-Bold.json.gz
31305eec9835f9b33dbf37db4eff528f3b7d0b4ff051f691c5e1ed1a98c15d4a  spacing/TeXGyrePagellaX-BoldItalic.json.gz
```

参数提取自以下 Pagella X 字体（SHA-256）：

```text
3c1857b64342b89a585c6c065c0ba4a5c608d42c88b87bd5255b623d0128ef2d  TeXGyrePagellaX-Regular.otf
9cb8432910882fa9e417795597806d289f5b50322e5f2c3395f8325cccf47e8d  TeXGyrePagellaX-Italic.otf
824327ff1ffa8134a20ac7cdc212854aa69851af24ca3107c6ca7c73a7ae91af  TeXGyrePagellaX-Bold.otf
edb659487607638919866d51b226efc07816f8916ba4898d746ef0b4c8c89601  TeXGyrePagellaX-BoldItalic.otf
```

这些文件随原始 [GUST Font License](../licenses/GUST-FONT-LICENSE.txt)、[LPPL](../licenses/lppl.txt)、[作者与版权说明](../licenses/README-TeX-Gyre-Pagella.txt)和[原始清单](../licenses/MANIFEST-TeX-Gyre-Pagella.txt)保留；Pagella X 的扩展说明见 [MANIFEST-newpx.txt](../licenses/MANIFEST-newpx.txt)（newpx 按 LPPL 1.3 分发）。完整上游作品见 [CTAN TeX Gyre](https://ctan.org/tex-archive/fonts/tex-gyre) 与 [CTAN newpx](https://ctan.org/pkg/newpx)。

衍生字形设计保存在 `fontviber/` 的 Python 源码中。构建期间生成的轮廓仅用于内存处理；无需保存解码副本、历史字体或预生成的 Display / Mono 轮廓。
