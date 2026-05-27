# ComfyUI-Category-Tag-Selector

![Category Tag Selector screenshot](https://github.com/nobinBB/ComfyUI-Category-Tag-Selector/blob/main/assets/screenshot.gif)

YAMLのカテゴリ名をノード内に縦展開し、日本語ラベルで選択した項目を英語タグのカンマ区切り `STRING` として出力する ComfyUI カスタムノードです。

選択した日本語ラベル自体も `title_text` として出力できます。  
また、YAML内の値に `{a|b|c}` のようなランダム選択構文を記載できます。

## Node

```txt
Category Tag Selector(nobin)
```

Category:

```txt
prompt/yaml
```

Output:

```txt
prompt: STRING
title_text: STRING
```

## Features

- `tags/` フォルダ内の `.yml` / `.yaml` を選択
- `tags/` 配下のサブフォルダ内 `.yml` / `.yaml` も読み込み可能
- YAMLのカテゴリ名をノード上に動的表示
- 各カテゴリの日本語ラベルをプルダウンで選択
- `prompt` 出力では、選択した項目に対応する英語タグをカンマ区切りで出力
- `title_text` 出力では、選択した日本語ラベルをカンマ区切りで出力
- `{a|b|c}` 形式のランダム選択構文に対応
- 直下カテゴリ形式と、単一ルートのネスト形式に対応
- `Refresh YAML Files` ボタンでYAMLファイル一覧を再取得
- `selections_json` はJS側で自動更新されます

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/nobinBB/ComfyUI-Category-Tag-Selector.git
cd ComfyUI-Category-Tag-Selector
pip install -r requirements.txt
```

ComfyUIを再起動してください。

## Recommended YAML format

```yaml
髪型:
  ショートヘア:
    - short hair
  ボブヘア:
    - bob hair

髪色:
  黒色:
    - black hair
  赤色:
    - red hair
```

この場合、ノードには以下のように表示されます。

```txt
髪型: [ショートヘア]
髪色: [赤色]
```

出力例:

```txt
prompt:
short hair, red hair,

title_text:
ショートヘア, 赤色,
```

## Supported nested YAML format

```yaml
髪のタイプ:
  髪型:
    ショートヘア:
      - short hair
  髪色:
    赤色:
      - red hair
```

単一ルート配下のカテゴリも読みます。

この場合も、ノード上には以下のように表示されます。

```txt
髪型: [ショートヘア]
髪色: [赤色]
```

出力例:

```txt
prompt:
short hair, red hair,

title_text:
ショートヘア, 赤色,
```

## Subfolder YAML files

`tags/` 配下のサブフォルダにある `.yml` / `.yaml` も読み込みできます。

例:

```txt
tags/
  sample_hair.yml
  eye/
    sample_eye.yml
  pose/
    basic_pose.yml
  outfit/
    casual.yml
```

ノードの `yaml_file` では、以下のような相対パスで表示されます。

```txt
sample_hair.yml
eye/sample_eye.yml
pose/basic_pose.yml
outfit/casual.yml
```

サブフォルダでYAMLを分類できるため、髪・目・服装・表情・ポーズなどを分けて管理できます。

## Outputs

```txt
prompt: STRING
title_text: STRING
```

### prompt

選択した日本語ラベルに対応する英語タグをカンマ区切りで出力します。

例:

```txt
short hair, red hair,
```

### title_text

選択した日本語ラベル自体をカンマ区切りで出力します。

例:

```txt
ショートヘア, 赤色,
```

日本語での確認用、ログ保存、記事用の見出し、画像ファイル名用の補助テキストとして利用できます。

## Random choice syntax

YAMLのタグ値には、`{a|b|c}` 形式のランダム選択構文を記載できます。

```yaml
目の色:
  ランダム色:
    - "{blue eyes|red eyes|green eyes|golden eyes}"

目の形:
  ランダム形:
    - "{large eyes|half-closed eyes|round eyes}"
```

この場合、実行時に `{}` 内の候補から1つだけ選択されます。

出力例:

```txt
red eyes, large eyes,
```

次回実行時には、以下のように別候補が選ばれる場合があります。

```txt
golden eyes, half-closed eyes,
```

### Multiple random choices

1つのタグ値の中に複数の `{a|b|c}` を書くこともできます。

```yaml
表情:
  ランダム表情:
    - "{smile|soft smile|serious}, {blush|light blush}"
```

出力例:

```txt
soft smile, light blush,
```

### Notes for random choice

- 対応形式は `{a|b|c}` のような単純な選択構文です。
- ネストした `{a|{b|c}}` のような形式は非推奨です。
- `{}` 内の候補は `|` で区切ります。
- 空の候補は避けてください。
- ComfyUIのキャッシュにより、同じ入力で再実行した場合に結果が変わらない場合があります。
- ランダム展開を毎回変えたい場合は、ノード側で `IS_CHANGED` による再実行対策を有効にしてください。

## Options

### yaml_file

`tags/` 内のYAMLファイルを選択します。

例:

```txt
sample_hair.yml
eye/sample_eye.yml
pose/basic_pose.yml
outfit/casual.yml
```

### Refresh YAML Files

`tags/` フォルダ内のYAMLファイル一覧を再取得します。

ComfyUI起動後に `.yml` / `.yaml` ファイルを追加した場合や、サブフォルダ内にYAMLファイルを追加した場合に使用します。

例:

```txt
tags/
  eye/
    sample_eye.yml
```

を追加したあと、`Refresh YAML Files` を押すと、`yaml_file` の候補に以下のような項目が反映されます。

```txt
eye/sample_eye.yml
```

### separator

タグ間の区切り文字です。

初期値:

```txt
, 
```

出力例:

```txt
short hair, red hair,
```

### trailing_comma

ONの場合、末尾にもカンマを付けます。

```txt
short hair, red hair,
```

OFFの場合:

```txt
short hair, red hair
```

### selections_json

JS側で自動更新される内部用の選択状態です。

通常、手動で編集する必要はありません。

## YAML examples

### Eye type sample

```yaml
目のタイプ:
  目の形:
    大きな目:
      - large eyes
    つり目:
      - tsurime
    たれ目:
      - tareme
    ジト目:
      - half-closed eyes

  目の色:
    黒色:
      - black eyes
    茶色:
      - brown eyes
    青色:
      - blue eyes
    赤色:
      - red eyes
```

出力例:

```txt
prompt:
tsurime, red eyes,

title_text:
つり目, 赤色,
```

### Random eye sample

```yaml
目のタイプ:
  目の形:
    ランダム:
      - "{large eyes|tsurime|tareme|half-closed eyes}"

  目の色:
    ランダム:
      - "{black eyes|brown eyes|blue eyes|red eyes|golden eyes}"
```

出力例:

```txt
prompt:
tareme, golden eyes,

title_text:
ランダム, ランダム,
```

## Notes

- YAMLファイル名一覧はComfyUI起動時の `INPUT_TYPES` で取得します。
- ComfyUI起動後にYAMLファイルを追加した場合は、`Refresh YAML Files` ボタンで再取得できます。
- `tags/` 配下のサブフォルダ内 `.yml` / `.yaml` も読み込み対象です。
- 既存YAMLの中身を変更した場合、ノード作成時・YAML切替時・Refresh実行時に `/category_tag_selector/schema` から再取得します。
- ノードのカテゴリ行はフロントエンドJSで動的に追加しています。
- バックエンドには `selections_json` として選択状態を渡します。
- `title_text` は選択した日本語ラベルを出力します。カテゴリ名ではありません。
- `{a|b|c}` のランダム展開は `prompt` 側の英語タグ出力に対して使用します。

## License

MIT License