# Minecraft Texture & Resource Pack Creator

A beginner-friendly desktop app that lets anyone create Minecraft resource packs for **both Java and Bedrock Edition** — retexture blocks, items, and mobs, add custom 3D models, set up random mob skins, and more. No knowledge of Minecraft's file structure required — the tool handles all folder paths, config files, and naming automatically.

## How It Works

1. **Pick what to change** — Replace textures, add custom models, or set up random mob skins from guided wizards.
2. **Drop in your files** — Browse or drag & drop PNGs, `.jem` models, and more straight from Explorer.
3. **Choose your edition** — Java, Bedrock, or Both at once.
4. **Click Generate** — The app creates the full pack with correct file names, folder structure, config files, and everything else.

## Features

### Core
- **Java + Bedrock support** — Generate packs for either edition or both simultaneously
- **Guided wizards** — Step-by-step dialogs for replacing textures, adding models, and setting up random skins
- **200+ built-in assets** — Blocks, items, entities, armor, GUI, environment, paintings
- **Drag & drop** — Drag files straight from Explorer onto the app — textures, models, or entire folders are auto-classified
- **Built-in Help guide** — "? Help" button with instructions on naming conventions, mod dependencies, and how each feature works

### Texture Replacement
- **Replace a Texture** wizard — Pick a category, search for the asset, choose your PNG
- **Auto-generates support files** — Item model JSONs, blockstate files, `pack.mcmeta`, `manifest.json`, and more

### Custom Models
- **Add Custom Model** wizard — Select all your model + texture files at once; the tool auto-classifies them
- **CEM support** — OptiFine Custom Entity Models (`.jem` files) placed in the correct `optifine/cem/` folder
- **Item & Block models** — Standard `.json` models for items and blocks
- **Auto-detect model type** — `.jem` files are automatically identified as CEM; `.json` files can be entity, item, or block

### Random Mob Skins
- **Multi-Skin wizard** — Give any mob multiple looks with an easy-to-use interface
- **4 methods supported**:
  - **Random Skins** — Same 3D shape, different textures picked at random (weighted chance)
  - **Random Models** — Different 3D shapes, each with its own texture (e.g. SwampEnderman-style packs)
  - **Nametag** — Skin changes when you name a mob with a nametag
  - **Mixed** — Combine random spawns + nametag-triggered variants
- **Auto-generates `.properties` files** — Correct `textures.<n>=` or `models.<n>=` syntax with weights
- **Emissive texture detection** — Automatically finds `_e.png` glow maps and generates `emissive.properties`
- **Smart field visibility** — UI only shows relevant fields for the selected method (weights for random, nametag field for nametag, etc.)

### Pack Generation
- **Pack icon support** — Set a custom icon with one click
- **Ready-to-install output** — `.zip` for Java, `.mcpack` for Bedrock (double-click to install!)
- **Up-to-date versions** — Java 1.13 through 26.2 (Chaos Cubed), Bedrock 1.16.100 through 26.32
- **Live version updates** — Fetch the latest Minecraft versions from Mojang's API with one click
- **New versioning support** — Handles both the new `year.drop` format (26.x) and legacy `1.x` versioning
- **Correct pack.mcmeta format** — Automatically uses `min_format`/`max_format` for 1.21.9+, or `pack_format`/`supported_formats` for older versions
- **Advanced mode** — "Add Custom File" for power users with preset path buttons

## Quick Start

```bash
pip install tkinterdnd2
python main.py
```
Or double-click `run.bat` on Windows.

### Step-by-Step

1. **Set pack name, description, edition, and version** at the top
2. Use one of the wizard buttons:
   - **"Replace a Texture..."** — Swap a vanilla texture
   - **"Add Custom Model..."** — Add a `.jem` or `.json` model with textures
   - **"Random Mob Skins..."** — Set up multi-skin mobs
   - **"Add Custom File..."** — Advanced manual file placement
3. Or **drag & drop** files directly from Explorer onto the file list
4. Optionally set a **Pack Icon** and **Output Folder**
5. Click **"Generate Resource Pack"**

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
| `*.properties` files | Random entity configs, emissive configs (auto-generated) |
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

## Mod Dependencies

Some features require specific mods to work in-game:

### OptiFine (or alternatives) — Required for:
- Custom Entity Models (`.jem` files)
- Random mob skins / textures
- Emissive textures (`_e` glow maps)
- `.properties` config files

Download from [optifine.net](https://optifine.net)

### Fabric/Quilt Alternatives
If you use Fabric instead of OptiFine:
- **Entity Model Features (EMF)** — for custom `.jem` models
- **Entity Texture Features (ETF)** — for random/emissive textures
- **CIT Resewn** — for custom item textures

All available on [Modrinth](https://modrinth.com) or [CurseForge](https://curseforge.com).

### No Mods Needed
These features work in vanilla Minecraft:
- Replacing block, item, and mob textures
- Custom item/block model `.json` files
- Pack icons and metadata

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

## Building a Standalone .exe

To distribute the app as a single executable:

```bash
pip install pyinstaller tkinterdnd2
pyinstaller ResourcePackCreator.spec --clean
```

Or just double-click **`build.bat`** — it installs dependencies and builds automatically. The output will be at `dist/ResourcePackCreator.exe`.

## Requirements

- Python 3.7+
- tkinter (included with standard Python on Windows/macOS)
- `tkinterdnd2` (optional — enables drag & drop; install with `pip install tkinterdnd2`)

## Tips

- **PNG format** is recommended for all textures (both Java and Bedrock use PNG natively)
- **Item textures** should be 16×16 pixels (or multiples like 32×32, 64×64)
- **Entity textures** have specific dimensions per mob — match the vanilla texture size
- **Armor textures** (Layer 1/Layer 2) are 64×32 pixels
- **`.jem` model filenames** must match the entity name (e.g. `enderman.jem`, `creeper.jem`)
- **Random model variants** are numbered: `enderman.jem`, `enderman2.jem`, `enderman3.jem`
- **Emissive textures** use the `_e` suffix: `enderman.png` → `enderman_e.png` for glow
- Choosing **"Both"** edition generates two separate folders (`_Java` and `_Bedrock`) with correctly formatted files for each
- Click **"? Help"** in the app for a full guide on naming, mod requirements, and features
