# HHKB Topre 键帽 3MF 生成包

这是一个面向拓竹 `P1SC` / Bambu Studio 的 HHKB 风格 Topre 键帽生成包。当前只导出 `3MF` 文件，适合直接导入 Bambu Studio 或 OrcaSlicer 做首轮试打。

模型几何参考了 CC0 许可的 [`fernandodeperto/topre_key`](https://github.com/fernandodeperto/topre_key)。当前 CadQuery 版本按该项目的思路实现：圆角底面 base 和带 row 倾角的顶面 base 做 loft，然后挖内部空腔、裁切圆柱凹面，并添加 Topre 圆筒开槽 connector。

## 输出内容

脚本会为每种键帽形状导出一个标准 connector 配合版本：

- `fit-nominal`：标准尺寸

生成后的 3MF 会自动焊接重复顶点，避免 Bambu Studio 报非流形边。

## 支持的键帽形状

当前会生成 HHKB US 配列需要的 11 种几何类型。每种类型导出一个 `fit-nominal` 标准版，因此本地 `output/` 里会生成 11 个 `.3mf` 文件。

- `row-e-1u`：顶排 Esc / 数字 / 符号区 1u
- `row-d-1u`：QWERTY 排普通 1u
- `tab-1_5u-row-d`：Tab / Delete 尺寸
- `row-c-1u`：ASDF 排普通 1u
- `control-1_75u-row-c`：Control 尺寸
- `return-2_25u-row-c`：Return 尺寸
- `row-b-1u`：ZXCV 排普通 1u / Fn
- `rshift-1_75u-row-b`：右 Shift 尺寸
- `lshift-2_25u-row-b`：左 Shift 尺寸
- `mod-1_5u-row-a`：底排 Alt / Cmd 尺寸
- `space-6u-row-a`：6u Space 原型

输出文件位于 `output/` 目录，命名格式类似：

```text
hhkb-topre-hhkb-style-space-6u-row-a-fit-nominal.3mf
```

## 使用方法

如果只想打印，直接打开 `output/` 中的 `.3mf` 文件即可。

如果需要重新生成模型：

```bash
UV_CACHE_DIR=.uv-cache uv venv .venv
UV_CACHE_DIR=.uv-cache uv pip install --python .venv/bin/python cadquery
.venv/bin/python cad/hhkb_topre_1u_keycap.py
```

生成完成后会得到：

- `output/*.3mf`：可导入 Bambu Studio / OrcaSlicer 的模型文件
- `output/hhkb-topre-hhkb-style-manifest.json`：本次导出的参数和文件清单

`output/` 是生成产物，已在 `.gitignore` 中排除；仓库只跟踪生成脚本和说明文档。

## 打印建议

- 打印机：Bambu Lab `P1SC`
- 材料：`PLA` 或 `PLA+`
- 喷嘴：`0.4 mm`
- 层高：建议 `0.12 mm`
- 壁数：建议 `3`
- 顶/底层：建议 `5 / 4`
- 支撑：首轮建议关闭
- 摆放方向：键帽顶部朝上
- 试配版本：`fit-nominal`

## 设计参数

- 1u 底部外形参考 `topre_key` 的 `18.00 mm` 基准
- 宽键按 HHKB 常见键长和 `19.05 mm` pitch 扩展
- row 高度、front angle、top angle、顶面长度计算、圆柱凹面和 connector 高度均参考 `topre_key`
- Topre connector 使用 `2.85 mm` 外半径、`1.00 mm` 壁厚、`-1.35 mm` 下探、`1.50 mm` 中槽
- 顶面凹面为圆柱凹面，sagitta 为 `0.60 mm`

## 重要限制

`fernandodeperto/topre_key` 本身只实现了一个居中的 Topre connector；仓库里的 `support` 是 CNC 加工用的外部支撑，不是键盘稳定器结构。因此本项目的 Topre connector 也直接按该仓库范围实现：每个键帽只有中心 Topre connector。

`space`、`return`、`shift` 等宽键的外形可以直接用于打印和中心轴试配，但它们没有额外添加 HHKB 原厂宽键稳定器结构。也就是说：中心轴能装并不代表宽键已经等同完整 OEM 替换件；如果你的实际键盘宽键依赖两侧稳定器，当前版本还需要下一轮按实物尺寸补稳定器接口。

`KeyV2` 里的 `spacebar()` / `stabilized()` 是 Cherry/Costar 稳定器体系，默认给宽键添加 MX/Costar 位置和接口，不是 Topre HHKB 原厂稳定器。为避免生成错误接口，当前不会把 KeyV2 的 Cherry/Costar 稳定器直接套进 Topre 模型。

如果 `fit-nominal` 偏松或偏紧，优先调整 `cad/hhkb_topre_1u_keycap.py` 里的 connector 参数或 `FIT_VARIANTS`，不要先改外形。

## 来源与许可

- 参考模型：[`fernandodeperto/topre_key`](https://github.com/fernandodeperto/topre_key)
- 参考模型许可：`CC0-1.0`
- 当前生成脚本：CadQuery 参数化实现
