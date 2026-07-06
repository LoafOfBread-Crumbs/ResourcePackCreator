# Minecraft Resource Pack Creator

A beginner-friendly desktop app that lets anyone create Minecraft resource packs for **both Java and Bedrock Edition**. No knowledge of Minecraft's file structure required — just pick what you want to retexture, choose your image, and generate.

## How It Works

1. **Pick what to replace** — Choose from a searchable list of blocks, items, mobs, armor, GUI elements, and more.
2. **Drop in your image** — Select the PNG you've drawn/edited.
3. **Choose your edition** — Java, Bedrock, or Both at once.
4. **Click Generate** — The app handles file names, folder structure, model files, and everything else automatically.

## Features

- **Java + Bedrock support** — Generate packs for either edition or both simultaneously
- **Guided wizard** — Step-by-step "Replace a Texture" dialog with categories and search
- **200+ built-in assets** — Blocks, items, entities, armor, GUI, environment, paintings
- **Auto-generates ALL support files** — The app creates every technical file your pack needs:
  - Java: `pack.mcmeta` (with `supported_formats` range), item model JSONs, blockstate files
  - Bedrock: `manifest.json` (with UUIDs), `terrain_texture.json`, `item_texture.json`, `textures_list.json`
- **Pack icon support** — Set a custom icon with one click (`pack.png` for Java, `pack_icon.png` for Bedrock)
- **Ready-to-install output** — `.zip` for Java, `.mcpack` for Bedrock (double-click to install!)
- **Up-to-date versions** — Java 1.13 through 26.2 (Chaos Cubed), Bedrock 1.16.100 through 26.32
- **New versioning support** — Handles both the new `year.drop` format (26.x) and legacy `1.x` versioning
- **Correct pack.mcmeta format** — Automatically uses `min_format`/`max_format` for 1.21.9+, or `pack_format`/`supported_formats` for older versions
- **Advanced mode** — "Add Custom File" for power users (OptiFine `.properties`, CEM `.jem`, model JSONs)

## Quick Start

```bash
python main.py
```
Or double-click `run.bat` on Windows.

### Step-by-Step

1. **Set pack name, description, edition, and version** at the top
2. Click **"Replace a Texture..."**
3. Pick a category (Blocks, Items, Entities, etc.)
4. Search or scroll to find what you want to retexture (e.g., "Diamond Sword")
5. Browse to your replacement image file
6. Click **"Add Replacement"** — repeat for as many textures as you like
7. Optionally set a **Pack Icon** and **Output Folder**
8. Click **"Generate Resource Pack"**

Your pack is ready to install!

## What Gets Generated Automatically

The app takes care of all the technical files so you don't have to:

### Java Edition
| What | Why It's Needed |
|------|----------------|
| `pack.mcmeta` | Pack metadata with format version and compatibility range |
| `pack.png` | The icon shown in the resource pack list |
| Item model `.json` files | Required for custom item textures to display |
| Blockstate `.json` files | Required for custom block models to load |
| Correct file names & paths | Minecraft requires exact names in exact folders |

### Bedrock Edition
| What | Why It's Needed |
|------|----------------|
| `manifest.json` | Pack metadata with UUIDs and engine version |
| `pack_icon.png` | The icon shown in the resource pack list |
| `terrain_texture.json` | Maps block texture names to their image files |
| `item_texture.json` | Maps item texture names to their image files |
| `textures_list.json` | Enumerates all textures in the pack |
| Correct folder paths | Bedrock uses different paths than Java (e.g., `textures/blocks/` not `textures/block/`) |

## Installing Your Pack

### Java Edition
1. Open Minecraft → Options → Resource Packs
2. Click **"Open Pack Folder"**
3. Copy the generated `.zip` into that folder
4. Select your pack in the list and click **Done**

### Bedrock Edition (Windows 10/11, Mobile, Console)
1. **Double-click** the generated `.mcpack` file — Minecraft imports it automatically
2. Or manually copy the pack folder into:
   - **Windows**: `%localappdata%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\resource_packs\`
   - **Android**: `games/com.mojang/resource_packs/`
   - **iOS**: `Minecraft/games/com.mojang/resource_packs/`
3. Go to Settings → Global Resources → Activate your pack

## Advanced: Custom Files

Click **"Add Custom File..."** to manually add:
- **Model JSON** files (`.json`) — auto-detects item vs block vs blockstate
- **OptiFine CIT properties** (`.properties`) — Java only
- **OptiFine CEM models** (`.jem`) — Java only
- **Any other file** with manual path control and preset buttons

> **Note**: OptiFine/Iris features (CIT, CEM, random mobs) are Java Edition only and will be skipped when generating a Bedrock pack.

## Requirements

- Python 3.7+
- tkinter (included with standard Python on Windows/macOS)

## Tips

- **PNG format** is recommended for all textures (both Java and Bedrock use PNG natively)
- **Item textures** should be 16×16 pixels (or multiples like 32×32, 64×64)
- **Entity textures** have specific dimensions per mob — match the vanilla texture size
- **Armor textures** (Layer 1/Layer 2) are 64×32 pixels
- Choosing **"Both"** edition generates two separate folders (`_Java` and `_Bedrock`) with correctly formatted files for each
- For **OptiFine features** (CIT, CEM, random mobs), use "Add Custom File" and install OptiFine or Iris in-game (Java only)
