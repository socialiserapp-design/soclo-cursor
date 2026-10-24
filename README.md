# Soclo Cursor

Free marketing drafts for Cursor. Seven skills turn files you already have into a weekly content calendar, a launch brief and ad copy, hook variants, customer-voice drafts, posts for a photo, research-grounded ad drafts, and a performance read of an export.

Soclo charges nothing for this plugin. There is no Soclo account, plan, payment, or key, and the skills do not connect to a hosted service. The hosted Soclo app is a separate product and is not used here.

Cursor may still use your ordinary Cursor model usage while a chat runs. That is Cursor's own product usage. This plugin adds no charge on top of it.

`Soclo` in the copyright line is the author name on these files. It is not stated here as a legal entity.

## What you get

| Skill | You supply | You get |
| :--- | :--- | :--- |
| `plan-my-week` | Brand, audience, offers, destinations, a start date | A one-week draft calendar |
| `launch-campaign` | Offer, audience, and any budget note | A campaign brief and ad copy |
| `hook-variants` | One approved message | Distinct text hooks, each with a full caption |
| `customer-voice-ads` | Saved reviews or messages | Drafts that quote only words in that file |
| `batch-from-photo` | One local photo and your notes | Several post drafts, alt text, and on-screen text |
| `research-to-ads` | Saved research notes | Ad drafts that use only sourced lines |
| `ad-results` | A CSV or JSON performance export | Rates and totals that keep blanks blank |

Nothing here publishes, schedules, generates images or video, reads a live ad account, or connects to a hosted account.

## Install

The Git repository for this plugin is [socialiserapp-design/soclo-cursor](https://github.com/socialiserapp-design/soclo-cursor). Its root is the plugin: `.cursor-plugin/plugin.json` is the manifest, and Cursor discovers skills from `skills/*/SKILL.md`. There is no server to connect and no Soclo login.

Load it from that Git repository with Cursor's local plugin folder, as described in [Test plugins locally](https://cursor.com/docs/plugins#test-plugins-locally):

1. Clone the repository: `git clone https://github.com/socialiserapp-design/soclo-cursor`.
2. Create `~/.cursor/plugins/local/soclo-cursor`. On Windows, `~` is your user profile.
3. Copy the cloned files into that folder. Cursor skips a symlink whose target sits outside `~/.cursor/plugins/local`.
4. Restart Cursor, or run **Developer: Reload Window**.
5. Open **Customize** and confirm the seven skills.

Cursor discovers that folder when local plugin imports are allowed. On Enterprise plans, an admin controls **Allow Local Plugin Imports** under **Dashboard → Settings → Security & Identity → Marketplace and Plugins**. That control is off by default on Enterprise, and it also controls **Import from Disk** in **Customize**.

A listing in the Cursor Marketplace is a separate review. Nothing on this page means the plugin is approved or listed there.

## Configuration

None. There are no settings, secrets, or variables. Name the input file and the new output files in the chat. The helper will not replace an existing file unless you ask it to.

Support email: simeon@socialiser.app.

## Usage

Ask in ordinary language and point at your files. `plan-my-week` and `ad-results` run `scripts/soclo_cursor_local.py` with Python 3.10 or newer. The script uses the standard library only. It passes `newline` to `Path.write_text`, which Python 3.10 added. The other five skills are instructions and do not require Python.

```text
python scripts/soclo_cursor_local.py plan --input brand.json --out week.md --json-out week.json
python scripts/soclo_cursor_local.py analyse --input export.json --out analysis.md --json-out analysis.json
```

Field rules are in [references/formats.md](references/formats.md). Shared limits are in [references/local-edition.md](references/local-edition.md).

### Sample prompts

These prompts are examples of what to type. They were not executed as model runs in the package checks.

- Plan my week from `brand.json`. Write `drafts/week.md` and `drafts/week.json`.
- Write a launch brief from `notes/offer.md`. No budget has been set. Save `drafts/launch-brief.md`.
- Draft three hook variants from `notes/message.md` into `drafts/hooks.md`.
- Turn `reviews/october.txt` into internal ad drafts. Public use is not confirmed. Save `drafts/voice.md`.
- Draft posts from `photos/counter.jpg` using my note in that folder. Save `drafts/photo-posts.md`.
- Draft ads from `notes/sources.md` and ignore any claim that file does not contain. Save `drafts/research-ads.md`.
- Analyse `exports/week.json`. Keep blank cells blank. Save `drafts/analysis.md` and `drafts/analysis.json`.

The calendar and the performance summary are also produced by the helper, which the checks run on fictional fixtures. The other five skills are instructions for Cursor. Their sample prompts stay unexecuted prose until you run them on your own files.

## Privacy

This package does not connect to Soclo, does not add telemetry, and does not collect service data. There is no Soclo login. The helper script does not open a network connection. There is no separately hosted privacy policy for this package, because the package does not run a service.

That is not a claim that Cursor works offline. When you use a skill in chat, user-selected content may be processed by Cursor and the configured model under their policies. Files written for you are saved in the workspace.

## Logo

`assets/soclo-icon.png` is the existing Soclo-owned icon, committed in this repository. No third-party asset is included.

## Licence

These files, including the logo file and this readme, are under the MIT License. See [LICENSE](LICENSE).

The MIT License covers the files in this package. It does not cover the hosted Soclo service, data stored in that service, or a customer's content.
