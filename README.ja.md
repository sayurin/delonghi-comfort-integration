# Home Assistant 用 De'Longhi Comfort

[![English](https://img.shields.io/badge/lang-en-lightgrey)](README.md)
[![日本語](https://img.shields.io/badge/lang-ja-blue)](README.ja.md)
[![Validate](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/sayurin/delonghi-comfort-integration)](https://github.com/sayurin/delonghi-comfort-integration/blob/main/LICENSE)
[![Version](https://img.shields.io/github/v/release/sayurin/delonghi-comfort-integration)](https://github.com/sayurin/delonghi-comfort-integration/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/sayurin/delonghi-comfort-integration/latest/total)](https://github.com/sayurin/delonghi-comfort-integration/releases/latest)
[![Stars](https://img.shields.io/github/stars/sayurin/delonghi-comfort-integration?style=flat&color=gold)](https://github.com/sayurin/delonghi-comfort-integration)

デロンギ マルチダイナミックヒーター用の、非公式 Home Assistant
インテグレーションです。**Home Assistant 2026.11.0 以降**、
De'Longhi Comfort アカウントとインターネット接続が必要です。

非公式クラウド API を利用しているため、仕様変更やサービス終了により
動作しなくなる可能性があります。デロンギによる提供・保証はありません。
ヒーター本体の安全機能の代わりとして使用しないでください。

## 対応するデロンギアプリについて

Home Assistant 上の表示名はいずれも **De'Longhi Comfort** ですが、
対応するアプリは異なります。本リポジトリは従来の
**De'Longhi Comfort** アプリに対応します。一方、Marketplace に標準掲載されている
[comfort-hub/delonghi-comfort-ha](https://github.com/comfort-hub/delonghi-comfort-ha)
は **De'Longhi Comfort** を名乗っていながら、従来の **De'Longhi Comfort**
アプリには対応せず、新しい **My Comfort Hub** アプリに対応します。両者は互換ではなく、
同じインテグレーションドメインを使うため同時にはインストールできません。
インストール時は、名前だけでなく対応アプリも確認してください。

## 機能と制限

- 対応する `DL-heater` を操作できます。暖房・停止、10～28℃の設定（0.5℃刻み）、
  プリセット、出力上限、室温、画面の明るさ、エコモード、チャイルドロックに対応します。
- 英語・日本語表示に対応します。更新間隔は **5～300秒**で設定でき、
  既定値は機器ごとに60秒です。認証情報が失効した場合は Home Assistant の
  再認証画面から更新できます。
- 出力操作では上限を設定し、現在の出力値を表示します。温度制御中は、
  現在の出力値が設定した上限を下回ることがあります。
- 週間スケジュール、OFFタイマー、アラーム、温度単位の操作には対応していません。
  これらはアプリまたはヒーター本体から操作してください。未対応モデルには操作を
  提供せず、アカウント内の機器がすべて未対応の場合は設定できません。
- 実機での動作確認は MDHAA15WIFI-BK で行っています。他の機種や認証失効・復旧の
  すべてのケースを実機で確認したものではありません。

## インストール

本インテグレーションは Marketplace の標準カタログには掲載されていません。
Home Assistant に組み込まれている **Marketplace** のカスタムリポジトリ機能から
インストールできます。

1. **Marketplace > インテグレーション**を開き、**カスタムリポジトリ**を選択します。
2. `https://github.com/sayurin/delonghi-comfort-integration` を
   **Integration** として追加します。
3. **De'Longhi Comfort** をインストールし、必要に応じて Home Assistant を再起動します。
4. **設定 > デバイスとサービス > インテグレーションを追加**から
   **De'Longhi Comfort** を選び、アカウント情報を入力します。

`delonghi_comfort` ドメインを使う他のインテグレーションと同時にインストールしないでください。

## 診断とサポート

アカウントまたはデバイスのメニューから診断情報をダウンロードできます。
アカウント診断にはアカウント内の全機器、デバイス診断には選択した機器だけが含まれます。
診断取得によって機器の操作や登録は行われません。識別子・認証情報・未知の文字列は
除去または匿名化されますが、数値や一部のモデル・バージョン情報は残ります。
共有する前にファイル全体を確認してください。

問題は [Issues](https://github.com/sayurin/delonghi-comfort-integration/issues) に、
Home Assistant とインテグレーションのバージョン、機種、問題の説明、匿名化したログを添えて
報告してください。パスワード・トークン・メールアドレス・DSN・シリアル番号は共有しないでください。
Home Assistant の Config Entry 保存は暗号化を保証しません。設定・バックアップ・ログを保護してください。

## ライセンス

ライセンスと第三者著作物の表示については、[LICENSE](LICENSE) と [NOTICE](NOTICE) を参照してください。
