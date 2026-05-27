# ComfyUI-Category-Tag-Selector
![Category Tag Selector screenshot](https://github.com/nobinBB/ComfyUI-Category-Tag-Selector/blob/main/assets/screenshot.gif)

YAMLのカテゴリ名をノード内に縦展開し、日本語ラベルで選択した項目を英語タグのカンマ区切り `STRING` として出力する ComfyUI カスタムノードです。

## Node

```txt
Category Tag Selector
```

Category:

```txt
prompt/yaml
```

Output:

```txt
text: STRING
```

## Features

- `tags/` フォルダ内の `.yml` / `.yaml` を選択
- YAMLのカテゴリ名をノード上に動的表示
- 各カテゴリの日本語ラベルをプルダウンで選択
- 選択した値を `short hair, red hair,` のように出力
- 直下カテゴリ形式と、単一ルートのネスト形式に対応
- `selections_json` はJS側で自動更新されます

## Install

```bash
cd ComfyUI/custom_nodes
git clone <this repository>
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
short hair, red hair,
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

## Options

### yaml_file

`tags/` 内のYAMLファイルを選択します。

### separator

タグ間の区切り文字です。初期値:

```txt
, 
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

## Notes

- YAMLファイル名一覧はComfyUI起動時の `INPUT_TYPES` で取得します。
- YAMLファイルを追加した場合は、基本的にComfyUI再起動が必要です。
- 既存YAMLの中身を変更した場合、ノード作成時・YAML切替時に `/category_tag_selector/schema` から再取得します。
- ノードのカテゴリ行はフロントエンドJSで動的に追加しています。
- バックエンドには `selections_json` として選択状態を渡します。
