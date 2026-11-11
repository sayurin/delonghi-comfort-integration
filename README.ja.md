# Home Assistant 用 De'Longhi Comfort

[English](README.md) |
[![Validate](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml)

[philm5/delonghi-comfort-integration](https://github.com/philm5/delonghi-comfort-integration)
から派生した、独立保守のマルチダイナミックヒーター用インテグレーションです。
**Home Assistant 2026.11.0 以降**、De'Longhi Comfort アカウントとインターネット接続が必要です。

**ライセンス・API 利用条件の確認が完了するまで公開リリースは保留中です。**
Marketplace の既定カタログには掲載されていません。
非公式クラウド API に依存し、サービス側の変更で動作しなくなる可能性があります。

## 機能と制限

- `DL-heater` のみ操作エンティティを作成します。暖房・停止、10～28℃の設定（0.5℃刻み）、
  プリセット、出力上限、室温、画面の明るさ、エコ、チャイルドロックに対応します。
- 英語・日本語表示に対応。更新間隔は **5～300 秒**、既定は機器ごとに5秒です。
  認証失効時には HA の再認証画面で更新できます。
- 出力操作は現在、**上限を設定し、現在出力を表示**します。温度制御により両者は異なります。
  操作・表示の分離は今後の課題です。
- 週間スケジュール、OFF タイマー、アラーム・温度単位の操作は未対応です。
  未対応モデルは操作せず、未対応機器だけのアカウントは設定できません。
- MDHAA15WIFI-BK の操作・再読込と英語／日本語表示を人間が確認しています。
  API モデル名 `MDH Wifi`／`MDH15 Wifi` の匿名化した各32項目の fixture が
  `tests/fixtures/` にあります。全機種や認証失効・復旧を実機検証したものではありません。

## インストール

承認されたリリースが**公開された後**に行います。

1. **Marketplace > メニュー > カスタムリポジトリ**で
   `https://github.com/sayurin/delonghi-comfort-integration` を **Integration** として追加します。
2. **De'Longhi Comfort** をインストールし、HA を再起動します。
3. **設定 > デバイスとサービス**から **De'Longhi Comfort** を追加し、アカウント情報を入力します。

Marketplace は互換性のための `hacs.json` に従い、`delonghi_comfort.zip` を取得します。
ドラフトや既定ブランチからはこの方法でインストールできません。
手動導入では ZIP を `config/custom_components/delonghi_comfort/` **の中へ**展開します。
ZIP 直下に `manifest.json` があります。開発時はチェックアウトから同ディレクトリをコピーできます。
同じ `delonghi_comfort` ドメインを使う別のインテグレーションと共存させないでください。

## 更新時の注意・診断

アカウントとエンティティの unique ID は維持します。更新前に HA をバックアップしてください。
古い値を直接指定する automation・テンプレートは変更が必要です。

| 旧値 | 新値 |
| --- | --- |
| `Day mode`, `Night mode`, `Antifrost`, `Manual` | `day_mode`, `night_mode`, `antifrost`, `manual` |
| `0%`, `20%`, `40%`, `60%`, `80%`, `100%` | `"0"`, `"20"`, `"40"`, `"60"`, `"80"`, `"100"` |

出力値は文字列なので YAML では引用符を付けます。英語の表示名は変更していません。
生のクラウド情報を返す `extra_state_attributes` は廃止しました。
標準の climate 属性・専用エンティティ・診断情報を使用してください。
登録済みエンティティ名は強制変更しません。アカウントの言語と HA の表示言語は別です。

アカウントまたはデバイスのメニューから診断をダウンロードできます。
全体診断は未対応モデルを含む全機器、デバイス診断は対象機器だけを取得します。
操作やデバイス登録は行いません。識別子・認証情報・未知の文字列は除去または匿名化し、
数値と一部のモデル・バージョン情報を残します。個別取得の失敗はエラーとして記録し、
アカウント全体や認証の失敗時はダウンロードを中断します。
共有・fixture 化の前に、HA が付加する情報も含めて**ファイル全体**を確認してください。

問題は [Issues](https://github.com/sayurin/delonghi-comfort-integration/issues) に、
バージョン・型番・期待する動作と匿名化ログを添えて報告してください。
パスワード・トークン・メール・DSN・シリアルを公開しないでください。
Config Entry への保存は暗号化を保証しません。設定・バックアップ・ログを保護してください。

## 開発・リリース

Python 3.14 の仮想環境で、このリポジトリのルートから実行します。

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

起動確認は、独立した Home Assistant のテスト環境へ integration を導入して行います。
CI は HA 最低版・最新版のテスト、hassfest、旧名称の HACS validator を実行します。
オフラインテストは実機確認の代わりにはなりません。

コミットは Conventional Commits（`fix:`、`feat:`、破壊的変更は `feat!:` と説明）を使います。
`main` への push で release-please がバージョン・CHANGELOG 更新 PR を作成・更新します。
`version.txt`・リリース管理ファイル・integration のバージョンを同期します。
自動化だけの変更には `feat:` ではなく `ci:` または `chore:` を使います。

**PR タイトルも Conventional Commits 形式**にします。
例：`fix: handle expired sessions`、`feat: add a heater sensor`、
`docs: clarify installation`。通常は **Squash and merge** を使い、
PR タイトルを squash コミットの件名として維持します。
破壊的変更の説明（`BREAKING CHANGE:`）や意図的な `Release-As:` 指定は、
最終コミットの本文に残してください。
コミットの保持を明示的に求める PR では、例外としてマージコミットを使います。

リリース PR をマージすると、ドラフト Release を作成します。
別 job がその固定コミットをテスト・バージョン検証し、LICENSE・NOTICE を含む
Marketplace 用 ZIP だけを添付します。ソース一式は GitHub が自動生成します。
ZIP 作成失敗時は同じ run の **Re-run failed jobs** を使います。
失敗中・添付ファイル不足のドラフトを公開せず、成果物とノートの確認後に**人間が公開**します。
タグ push から重複して Release を作る workflow は使用しません。

公開には引き続き、ECAMpy 由来コードの許諾（[NOTICE](NOTICE)）と、
固定 API/client/app 値の由来・利用条件の確認が必要です。
公開済みコードであることは利用許諾の証明ではありません。
残る実機試験とクリーン環境への Marketplace ZIP 導入確認も必要です。
CI 成功だけでこれらを解決済みとは扱いません。

## ライセンス

[Apache-2.0](LICENSE)。[NOTICE](NOTICE) に記載する第三者コードの由来・許諾には未解決事項があります。
他者のコードのライセンスを推定しません。philm5、rtfpessoa/delonghi-comfort-client、
ECAMpy に帰属する認証処理を基にしています。コード・独自の汎用ラジエーター画像には AI を利用しました。
メーカー非公式・無保証です。機器自体の安全機能の代用にしないでください。
