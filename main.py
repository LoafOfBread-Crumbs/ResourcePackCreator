#!/usr/bin/env python3
"""
Minecraft Texture & Resource Pack Creator
User-friendly tool — no Minecraft file structure knowledge needed.
Pick what you want to retexture, drop in your image or custom model, generate.
Supports textures, custom entity models (CEM/JEM), item models, and more.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import shutil
import zipfile
import tempfile
import uuid
import threading
from pathlib import Path
from urllib.request import urlopen, Request
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
from urllib.error import URLError

# ─── Java Edition pack format versions ────────────────────────────────
# Since 1.21.9 (25w31a) the pack.mcmeta uses min_format/max_format
# instead of pack_format/supported_formats.  Versions marked True below
# use the new system; False use the legacy system.
#   key: display label
#   value: (resource_pack_format, uses_new_format_system)
JAVA_PACK_FORMATS = {
    # ── New year.drop versioning (2026+) ──
    "26.2 - Chaos Cubed (Latest)":       (88, True),
    "26.1 - 26.1.2 - Tiny Takeover":     (84, True),
    # ── Legacy 1.x versioning ──
    "1.21.11":                            (75, True),
    "1.21.9 - 1.21.10":                  (69, True),
    "1.21.7 - 1.21.8":                   (64, False),
    "1.21.6":                             (63, False),
    "1.21.5":                             (55, False),
    "1.21.4":                             (46, False),
    "1.21.2 - 1.21.3":                   (42, False),
    "1.21 - 1.21.1":                      (34, False),
    "1.20.5 - 1.20.6":                   (32, False),
    "1.20.3 - 1.20.4":                   (22, False),
    "1.20 - 1.20.2":                     (15, False),
    "1.19.4":                             (13, False),
    "1.19.3":                             (12, False),
    "1.19 - 1.19.2":                      (9, False),
    "1.18.x":                             (8, False),
    "1.17.x":                             (7, False),
    "1.16.2 - 1.16.5":                    (6, False),
    "1.15 - 1.16.1":                      (5, False),
    "1.13 - 1.14.4":                      (4, False),
}

# ─── Bedrock Edition version info ────────────────────────────────────
# Bedrock also switched to year.drop versioning in 2026.
# min_engine_version stays as [major, minor, patch] in manifest.json.
BEDROCK_VERSIONS = {
    # ── New year.drop versioning (2026+) ──
    "26.32 (Latest)":           [1, 26, 32],
    "26.30 - 26.31":            [1, 26, 30],
    "26.20":                    [1, 26, 20],
    "26.10":                    [1, 26, 10],
    "26.0":                     [1, 26, 0],
    # ── Legacy 1.x versioning ──
    "1.21.80":                  [1, 21, 80],
    "1.21.50 - 1.21.70":       [1, 21, 50],
    "1.21.0 - 1.21.40":        [1, 21, 0],
    "1.20.60 - 1.20.80":       [1, 20, 60],
    "1.20.0 - 1.20.50":        [1, 20, 0],
    "1.19.60 - 1.19.80":       [1, 19, 60],
    "1.19.0 - 1.19.50":        [1, 19, 0],
    "1.18.0 - 1.18.30":        [1, 18, 0],
    "1.17.0 - 1.17.40":        [1, 17, 0],
    "1.16.100 - 1.16.220":     [1, 16, 100],
}

# Backward compat alias (returns format int for legacy callers)
PACK_FORMATS = {k: v[0] for k, v in JAVA_PACK_FORMATS.items()}

# Resource pack format >= 65 means the version uses min_format/max_format
NEW_FORMAT_THRESHOLD = 65

# Cache file for fetched versions (next to main.py)
_VERSION_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "version_cache.json")

MOJANG_MANIFEST_URL = ("https://piston-meta.mojang.com/mc/game/"
                       "version_manifest_v2.json")


def _fetch_java_versions():
    """Fetch latest Java release versions + pack formats from Mojang API.
    Returns a dict like JAVA_PACK_FORMATS: {label: (format, uses_new)}."""
    req = Request(MOJANG_MANIFEST_URL,
                  headers={"User-Agent": "MC-ResourcePackCreator/1.0"})
    with urlopen(req, timeout=10) as resp:
        manifest = json.loads(resp.read())

    # Only care about release versions (not snapshots / old_alpha / old_beta)
    releases = [v for v in manifest["versions"] if v["type"] == "release"]

    # We only need versions newer than what we already have hardcoded.
    known_ids = set()
    for label in JAVA_PACK_FORMATS:
        # Extract bare version ids from labels like "26.2 - Chaos Cubed (Latest)"
        parts = label.split(" - ")[0].split(" ")[0]
        known_ids.add(parts)
        # Also handle ranges like "1.21.7 - 1.21.8"
        if " - " in label:
            after = label.split(" - ")[1].split(" ")[0]
            known_ids.add(after)

    new_versions = {}
    for ver in releases:
        vid = ver["id"]
        if vid in known_ids:
            continue
        # Fetch per-version JSON to get resource pack format
        try:
            vreq = Request(ver["url"],
                           headers={"User-Agent": "MC-ResourcePackCreator/1.0"})
            with urlopen(vreq, timeout=10) as vresp:
                vdata = json.loads(vresp.read())
            pv = vdata.get("pack_version", {})
            if isinstance(pv, dict):
                fmt = pv.get("resource", 0)
            elif isinstance(pv, (int, float)):
                fmt = pv
            else:
                continue
            fmt_int = int(fmt)
            if fmt_int < 4:
                continue  # too old
            uses_new = fmt_int >= NEW_FORMAT_THRESHOLD
            new_versions[vid] = (fmt_int, uses_new)
        except Exception:
            continue

    return new_versions


def _save_version_cache(versions_dict):
    """Save discovered versions to local cache JSON."""
    # Convert for JSON (tuples -> lists)
    data = {k: list(v) for k, v in versions_dict.items()}
    try:
        with open(_VERSION_CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_version_cache():
    """Load cached versions. Returns dict {label: (format, uses_new)} or {}."""
    try:
        with open(_VERSION_CACHE_PATH, "r") as f:
            data = json.load(f)
        return {k: tuple(v) for k, v in data.items()}
    except Exception:
        return {}


# ─── Minecraft asset database ────────────────────────────────────────
# Friendly name -> internal texture filename (no extension)

BLOCKS = {
    "Stone": "stone", "Granite": "granite", "Polished Granite": "polished_granite",
    "Diorite": "diorite", "Polished Diorite": "polished_diorite",
    "Andesite": "andesite", "Polished Andesite": "polished_andesite",
    "Grass Block (Top)": "grass_block_top", "Grass Block (Side)": "grass_block_side",
    "Dirt": "dirt", "Coarse Dirt": "coarse_dirt", "Podzol (Top)": "podzol_top",
    "Cobblestone": "cobblestone", "Mossy Cobblestone": "mossy_cobblestone",
    "Oak Planks": "oak_planks", "Spruce Planks": "spruce_planks",
    "Birch Planks": "birch_planks", "Jungle Planks": "jungle_planks",
    "Acacia Planks": "acacia_planks", "Dark Oak Planks": "dark_oak_planks",
    "Mangrove Planks": "mangrove_planks", "Cherry Planks": "cherry_planks",
    "Bamboo Planks": "bamboo_planks", "Crimson Planks": "crimson_planks",
    "Warped Planks": "warped_planks",
    "Sand": "sand", "Red Sand": "red_sand", "Gravel": "gravel",
    "Gold Ore": "gold_ore", "Iron Ore": "iron_ore", "Coal Ore": "coal_ore",
    "Diamond Ore": "diamond_ore", "Emerald Ore": "emerald_ore",
    "Lapis Ore": "lapis_ore", "Redstone Ore": "redstone_ore",
    "Copper Ore": "copper_ore", "Deepslate": "deepslate",
    "Deepslate Diamond Ore": "deepslate_diamond_ore",
    "Oak Log (Side)": "oak_log", "Oak Log (Top)": "oak_log_top",
    "Spruce Log": "spruce_log", "Birch Log": "birch_log",
    "Glass": "glass", "White Stained Glass": "white_stained_glass",
    "Bookshelf": "bookshelf", "Obsidian": "obsidian",
    "Crying Obsidian": "crying_obsidian",
    "TNT (Side)": "tnt_side", "TNT (Top)": "tnt_top",
    "Bricks": "bricks", "Stone Bricks": "stone_bricks",
    "Netherrack": "netherrack", "Soul Sand": "soul_sand",
    "Glowstone": "glowstone", "End Stone": "end_stone",
    "Bedrock": "bedrock", "Ice": "ice", "Packed Ice": "packed_ice",
    "Snow": "snow", "Clay": "clay",
    "Pumpkin (Side)": "pumpkin_side", "Melon (Side)": "melon_side",
    "Crafting Table (Top)": "crafting_table_top",
    "Crafting Table (Side)": "crafting_table_side",
    "Furnace (Front)": "furnace_front", "Furnace (Side)": "furnace_side",
    "Iron Block": "iron_block", "Gold Block": "gold_block",
    "Diamond Block": "diamond_block", "Emerald Block": "emerald_block",
    "Netherite Block": "netherite_block", "Copper Block": "copper_block",
    "Amethyst Block": "amethyst_block",
    "Ancient Debris (Side)": "ancient_debris_side",
}

ITEMS = {
    "Diamond Sword": "diamond_sword", "Iron Sword": "iron_sword",
    "Netherite Sword": "netherite_sword", "Wooden Sword": "wooden_sword",
    "Stone Sword": "stone_sword", "Golden Sword": "golden_sword",
    "Diamond Pickaxe": "diamond_pickaxe", "Iron Pickaxe": "iron_pickaxe",
    "Netherite Pickaxe": "netherite_pickaxe", "Wooden Pickaxe": "wooden_pickaxe",
    "Diamond Axe": "diamond_axe", "Iron Axe": "iron_axe",
    "Diamond Shovel": "diamond_shovel", "Iron Shovel": "iron_shovel",
    "Diamond Hoe": "diamond_hoe", "Iron Hoe": "iron_hoe",
    "Bow": "bow", "Arrow": "arrow", "Crossbow (Standby)": "crossbow_standby",
    "Trident": "trident", "Shield (Base)": "shield_base",
    "Diamond Helmet": "diamond_helmet", "Diamond Chestplate": "diamond_chestplate",
    "Diamond Leggings": "diamond_leggings", "Diamond Boots": "diamond_boots",
    "Iron Helmet": "iron_helmet", "Iron Chestplate": "iron_chestplate",
    "Netherite Helmet": "netherite_helmet",
    "Netherite Chestplate": "netherite_chestplate",
    "Apple": "apple", "Golden Apple": "golden_apple",
    "Enchanted Golden Apple": "enchanted_golden_apple",
    "Bread": "bread", "Cooked Beef": "cooked_beef",
    "Cooked Porkchop": "cooked_porkchop",
    "Ender Pearl": "ender_pearl", "Blaze Rod": "blaze_rod",
    "Nether Star": "nether_star", "Eye of Ender": "ender_eye",
    "Diamond": "diamond", "Emerald": "emerald",
    "Iron Ingot": "iron_ingot", "Gold Ingot": "gold_ingot",
    "Netherite Ingot": "netherite_ingot", "Copper Ingot": "copper_ingot",
    "Stick": "stick", "Bone": "bone", "String": "string",
    "Redstone Dust": "redstone", "Glowstone Dust": "glowstone_dust",
    "Compass": "compass", "Clock": "clock",
    "Map (Empty)": "map", "Book": "book", "Writable Book": "writable_book",
    "Fishing Rod": "fishing_rod", "Carrot on a Stick": "carrot_on_a_stick",
    "Spyglass": "spyglass", "Totem of Undying": "totem_of_undying",
    "Elytra": "elytra", "Name Tag": "name_tag",
    "Bucket": "bucket", "Water Bucket": "water_bucket",
    "Lava Bucket": "lava_bucket",
}

ENTITIES = {
    "Zombie": "zombie/zombie", "Skeleton": "skeleton/skeleton",
    "Creeper": "creeper/creeper", "Spider": "spider/spider",
    "Enderman": "enderman/enderman", "Blaze": "blaze",
    "Ghast": "ghast/ghast", "Slime": "slime/slime",
    "Phantom": "phantom", "Drowned": "zombie/drowned",
    "Husk": "zombie/husk", "Stray": "skeleton/stray",
    "Wither Skeleton": "skeleton/wither_skeleton",
    "Pig": "pig/pig", "Cow": "cow/cow", "Sheep (White)": "sheep/sheep",
    "Chicken": "chicken", "Wolf": "wolf/wolf",
    "Cat (Tabby)": "cat/tabby", "Horse (White)": "horse/horse_white",
    "Villager": "villager/villager", "Iron Golem": "iron_golem/iron_golem",
    "Witch": "witch", "Pillager": "illager/pillager",
    "Evoker": "illager/evoker", "Guardian": "guardian",
    "Bee": "bee/bee", "Fox": "fox/fox",
    "Axolotl (Lucy)": "axolotl/axolotl_lucy",
    "Frog (Temperate)": "frog/temperate_frog",
    "Warden": "warden/warden", "Sniffer": "sniffer/sniffer",
    "Ender Dragon": "enderdragon/dragon", "Wither": "wither/wither",
}

ARMOR_TEXTURES = {
    "Diamond Armor (Layer 1)": "diamond_layer_1",
    "Diamond Armor (Layer 2)": "diamond_layer_2",
    "Iron Armor (Layer 1)": "iron_layer_1",
    "Iron Armor (Layer 2)": "iron_layer_2",
    "Gold Armor (Layer 1)": "gold_layer_1",
    "Gold Armor (Layer 2)": "gold_layer_2",
    "Netherite Armor (Layer 1)": "netherite_layer_1",
    "Netherite Armor (Layer 2)": "netherite_layer_2",
    "Leather Armor (Layer 1)": "leather_layer_1",
    "Leather Armor (Layer 2)": "leather_layer_2",
    "Chainmail Armor (Layer 1)": "chainmail_layer_1",
    "Chainmail Armor (Layer 2)": "chainmail_layer_2",
}

GUI_TEXTURES = {
    "Inventory": "container/inventory", "Crafting Table": "container/crafting_table",
    "Furnace": "container/furnace", "Chest (Single)": "container/generic_54",
    "Anvil": "container/anvil", "Enchanting Table": "container/enchanting_table",
    "Brewing Stand": "container/brewing_stand",
    "Hotbar (Widgets)": "widgets", "Icons (Hearts etc)": "icons",
}

ENVIRONMENT_TEXTURES = {
    "Sun": "sun", "Moon Phases": "moon_phases", "Rain": "rain",
    "Snow (Particle)": "snow", "End Sky": "end_sky", "Clouds": "clouds",
}

PAINTING_TEXTURES = {
    "Alban": "alban", "Aztec": "aztec", "Aztec2": "aztec2", "Bomb": "bomb",
    "Burning Skull": "burning_skull", "Bust": "bust", "Courbet": "courbet",
    "Creebet": "creebet", "Donkey Kong": "donkey_kong",
    "Fighters": "fighters", "Graham": "graham", "Kebab": "kebab",
    "Match": "match", "Plant": "plant", "Pool": "pool",
    "Pointer": "pointer", "Sea": "sea", "Skeleton": "skeleton",
    "Stage": "stage", "Void": "void", "Wanderer": "wanderer",
    "Wither": "wither",
}

# Category name -> (asset_dict, pack_folder_path)
ASSET_CATEGORIES = {
    "Blocks": (BLOCKS, "assets/minecraft/textures/block"),
    "Items": (ITEMS, "assets/minecraft/textures/item"),
    "Entities / Mobs": (ENTITIES, "assets/minecraft/textures/entity"),
    "Armor (Worn on Body)": (ARMOR_TEXTURES, "assets/minecraft/textures/models/armor"),
    "GUI / Menus": (GUI_TEXTURES, "assets/minecraft/textures/gui"),
    "Environment / Sky": (ENVIRONMENT_TEXTURES, "assets/minecraft/textures/environment"),
    "Paintings": (PAINTING_TEXTURES, "assets/minecraft/textures/painting"),
}


# ═════════════════════════════════════════════════════════════════════
#  APPLICATION
# ═════════════════════════════════════════════════════════════════════

class ResourcePackGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft Texture & Resource Pack Creator")
        self.root.geometry("950x720")
        self.root.minsize(900, 650)

        # Each entry: {source_file, dest_path, display_name, category}
        self.entries = []
        self.pack_icon_path = None
        self._all_java_formats = dict(JAVA_PACK_FORMATS)

        self._create_styles()
        self._create_widgets()

    def _create_styles(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=10)

    # ─── UI ───────────────────────────────────────────────────────────

    def _create_widgets(self):
        main = ttk.Frame(self.root, padding="15")
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        # Header
        ttk.Label(main, text="Minecraft Resource Pack Creator",
                  style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(main, text="Add your textures below, then click Generate. "
                  "The app handles all file names, folders, and support files for you.",
                  style="Sub.TLabel", wraplength=800).grid(
                      row=1, column=0, sticky="w", pady=(0, 12))

        # ── Pack Settings ──
        settings = ttk.LabelFrame(main, text="Pack Settings", padding="8")
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        settings.columnconfigure(3, weight=1)

        # Row 0: Name + Description
        ttk.Label(settings, text="Pack Name:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.pack_name = tk.StringVar(value="MyResourcePack")
        ttk.Entry(settings, textvariable=self.pack_name, width=25).grid(
            row=0, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(settings, text="Description:").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=4)
        self.description = tk.StringVar(value="A custom Minecraft resource pack")
        ttk.Entry(settings, textvariable=self.description, width=35).grid(
            row=0, column=3, sticky="ew", padx=5, pady=4)

        # Row 1: Edition + Version
        ttk.Label(settings, text="Edition:").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        self.edition = tk.StringVar(value="Java")
        edition_combo = ttk.Combobox(
            settings, textvariable=self.edition,
            values=["Java", "Bedrock", "Both (Java + Bedrock)"],
            state="readonly", width=22)
        edition_combo.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        edition_combo.bind("<<ComboboxSelected>>", self._on_edition_change)

        ttk.Label(settings, text="Version:").grid(row=1, column=2, sticky="w", padx=(15, 5), pady=4)
        self._ver_frame = ttk.Frame(settings)
        self._ver_frame.grid(row=1, column=3, sticky="w", padx=5, pady=4)

        self.java_version = tk.StringVar(value="26.2 - Chaos Cubed (Latest)")
        self._java_ver_combo = ttk.Combobox(
            self._ver_frame, textvariable=self.java_version,
            values=list(JAVA_PACK_FORMATS.keys()), state="readonly", width=34)
        self._java_ver_combo.pack(side=tk.LEFT)

        self.bedrock_version = tk.StringVar(value="26.32 (Latest)")
        self._bedrock_ver_combo = ttk.Combobox(
            self._ver_frame, textvariable=self.bedrock_version,
            values=list(BEDROCK_VERSIONS.keys()), state="readonly", width=24)
        # Hidden by default (Java selected)

        self._update_btn = ttk.Button(
            self._ver_frame, text="\u21bb Update Versions",
            command=self._check_for_new_versions, width=18)
        self._update_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Merge any previously cached versions into the combo
        self._merge_cached_versions()

        # Row 2: Output folder
        ttk.Label(settings, text="Output Folder:").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        out_frame = ttk.Frame(settings)
        out_frame.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=4)
        out_frame.columnconfigure(0, weight=1)
        self.output_dir = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.output_dir,
                  state="readonly").grid(row=0, column=0, sticky="ew")
        ttk.Button(out_frame, text="Browse...",
                   command=self._browse_output).grid(row=0, column=1, padx=(4, 0))

        # Row 3: Pack icon
        icon_frame = ttk.Frame(settings)
        icon_frame.grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=4)
        ttk.Label(icon_frame, text="Pack Icon:").pack(side=tk.LEFT)
        self.icon_label = ttk.Label(icon_frame, text="(none — optional)")
        self.icon_label.pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(icon_frame, text="Choose Icon...",
                   command=self._choose_icon).pack(side=tk.LEFT)

        # ── Texture Replacements List ──
        list_frame = ttk.LabelFrame(main, text="Texture Replacements", padding="8")
        list_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        # Buttons
        btn = ttk.Frame(list_frame)
        btn.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Button(btn, text="Replace a Texture...",
                   command=self._wizard_replace, style="Action.TButton"
                   ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn, text="Add Custom Model...",
                   command=self._wizard_add_model, style="Action.TButton"
                   ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn, text="Random Mob Skins...",
                   command=self._wizard_random_entity, style="Action.TButton"
                   ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn, text="Add Custom File...",
                   command=self._add_custom_file
                   ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn, text="Remove Selected",
                   command=self._remove_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn, text="Clear All",
                   command=self._clear_all).pack(side=tk.LEFT)
        ttk.Button(btn, text="? Help",
                   command=self._show_help).pack(side=tk.RIGHT)

        # Treeview
        cols = ("what", "your_file", "category")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=14)
        self.tree.heading("what", text="What It Replaces")
        self.tree.heading("your_file", text="Your File")
        self.tree.heading("category", text="Category")
        self.tree.column("what", width=280)
        self.tree.column("your_file", width=350)
        self.tree.column("category", width=150)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

        self.tree.bind("<Delete>", lambda e: self._remove_selected())

        # Drag & drop zone
        if HAS_DND:
            drop_hint = ttk.Label(list_frame,
                text="📂 Drag & drop files here — textures, models, or whole folders",
                font=("Segoe UI", 9), foreground="#888888",
                anchor="center", relief="groove", padding=6)
            drop_hint.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
            # Register both the treeview and the hint as drop targets
            for widget in (self.tree, drop_hint):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._handle_drop)

        # ── Bottom bar ──
        bottom = ttk.Frame(main)
        bottom.grid(row=4, column=0, sticky="ew")

        self.zip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom, text="Also create ZIP (ready to install)",
                        variable=self.zip_var).pack(side=tk.LEFT)

        ttk.Button(bottom, text="Generate Resource Pack",
                   command=self._generate_pack,
                   style="Big.TButton").pack(side=tk.RIGHT)

        # Status
        dnd_hint = " or drag & drop files" if HAS_DND else ""
        self.status = tk.StringVar(
            value=f"Ready — click a button above{dnd_hint} to start")
        ttk.Label(main, textvariable=self.status, relief=tk.SUNKEN,
                  anchor=tk.W).grid(row=5, column=0, sticky="ew", pady=(8, 0))

    # ─── HELP ────────────────────────────────────────────────────────

    def _show_help(self):
        """Show a scrollable help/guide window."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Help & Guide")
        dlg.geometry("680x620")
        dlg.transient(self.root)

        ttk.Label(dlg, text="Resource Pack Creator — Help & Guide",
                  font=("Segoe UI", 13, "bold")).pack(pady=(12, 6))

        text = tk.Text(dlg, wrap="word", font=("Segoe UI", 10),
                       padx=16, pady=10, spacing2=2, spacing3=4)
        vsb = ttk.Scrollbar(dlg, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill="y")
        text.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))

        # Configure tags for formatting
        text.tag_configure("h1", font=("Segoe UI", 12, "bold"),
                           spacing1=12, spacing3=4)
        text.tag_configure("h2", font=("Segoe UI", 10, "bold"),
                           spacing1=8, spacing3=2)
        text.tag_configure("bullet", lmargin1=20, lmargin2=34)
        text.tag_configure("code", font=("Consolas", 9),
                           background="#f0f0f0", spacing1=2, spacing3=2)
        text.tag_configure("important", font=("Segoe UI", 10, "bold"),
                           foreground="#c0392b")

        def h1(t):
            text.insert("end", t + "\n", "h1")

        def h2(t):
            text.insert("end", t + "\n", "h2")

        def p(t):
            text.insert("end", t + "\n\n")

        def b(t):
            text.insert("end", "  \u2022  " + t + "\n", "bullet")

        def code(t):
            text.insert("end", "    " + t + "\n", "code")

        def imp(t):
            text.insert("end", t + "\n", "important")

        # ── Content ──
        h1("GETTING STARTED")
        p("This tool builds Minecraft resource packs for you. "
          "You provide the textures and models — it handles all the "
          "folder structure, config files, and pack.mcmeta automatically.")
        b("Replace a Texture — swap any vanilla block, item, or mob texture")
        b("Add Custom Model — add a 3D entity model (.jem) with its textures")
        b("Random Mob Skins — give a mob multiple random looks")
        b("Add Custom File — for advanced users, add any file manually")
        b("Drag & Drop — drag files from Explorer straight onto the list")

        h1("NAMING CONVENTIONS")
        h2("Textures")
        p("Minecraft textures are .png files. The tool places them in the "
          "correct folder for you, but your source files can be named anything.")
        b("For 'Replace a Texture': name doesn't matter — you pick the target from a list")
        b("For Custom Models: textures should match what the .jem file expects")
        b("For Random Skins: the tool auto-renames them (e.g. creeper.png, creeper2.png, creeper3.png)")

        h2("Models (.jem files)")
        p("Custom Entity Models (CEM) use .jem files made in Blockbench or "
          "similar tools. Key naming rules:")
        b("The .jem filename must match the entity name (e.g. enderman.jem, creeper.jem)")
        b("For random model variants: enderman.jem, enderman2.jem, enderman3.jem")
        b("Inside the .jem, the \"texture\" field must point to the right texture path")
        code('Example:  "texture": "textures/entity/enderman/enderman"')
        p("When using this tool, just make sure your .jem files have the "
          "correct texture paths inside them — the tool handles placement.")

        h2("Emissive Textures (glow-in-the-dark)")
        p("To make parts of a texture glow, create a copy with _e added "
          "to the filename:")
        b("enderman.png  \u2192  enderman_e.png  (the glowing parts)")
        b("creeper.png  \u2192  creeper_e.png")
        p("The tool will automatically detect _e textures and generate the "
          "required emissive.properties file.")

        h1("MOD DEPENDENCIES")
        imp("Important: Some features require specific mods to be installed!")
        p("")
        h2("OptiFine (or alternatives)")
        p("Required for:")
        b("Custom Entity Models (.jem files)")
        b("Random mob skins / textures")
        b("Emissive textures (_e glow maps)")
        b("The .properties config files this tool generates")
        p("Download OptiFine from: optifine.net\n"
          "Or use alternatives like: Continuity + Entity Model Features + "
          "Entity Texture Features (for Fabric/Quilt)")

        h2("Fabric/Quilt Alternative Mods")
        p("If you don't use OptiFine, you'll need these Fabric mods "
          "for the same features:")
        b("Entity Model Features (EMF) — for custom .jem models")
        b("Entity Texture Features (ETF) — for random/emissive textures")
        b("CIT Resewn — for custom item textures (if applicable)")
        p("All available on Modrinth or CurseForge.")

        h2("Vanilla Features (no mods needed)")
        p("These work without any mods:")
        b("Replacing block/item/mob textures (the basic 'Replace a Texture' feature)")
        b("Custom item models (.json)")
        b("Block model overrides (.json)")

        h1("RANDOM MOB SKINS — HOW IT WORKS")
        h2("Random Skins (same shape, different textures)")
        p("The mob keeps its normal 3D shape but gets a random texture "
          "each time it spawns. You set a weight (chance) for each variant.\n"
          "Example: 3 creeper skins with weights 10, 10, 5 — the third "
          "skin appears ~20% of the time.")

        h2("Random Models (different 3D shapes)")
        p("Each variant has its own .jem model AND its own texture. "
          "The game picks a random model on spawn, and that model uses "
          "its own texture.\n"
          "Example: SwampEnderman pack — 3 different enderman models, "
          "each with unique mushrooms/plants.")

        h2("Nametag Skins")
        p("The mob's appearance changes when you give it a specific name "
          "using a nametag. Great for easter eggs!\n"
          "Example: naming a creeper \"Steve\" gives it a special skin.")

        h2("Mixed Mode")
        p("Combine random + nametag: most mobs get a random skin, but "
          "specific names trigger special variants.")

        h1("TIPS & TROUBLESHOOTING")
        b("Make sure your .png textures are the correct resolution "
          "(most mob textures are 64x32 or 64x64)")
        b("Test your pack in a singleplayer world first")
        b("If textures look wrong, check the .jem file's \"textureSize\" "
          "matches your texture dimensions")
        b("Resource packs go in: .minecraft/resourcepacks/")
        b("You can layer multiple resource packs — higher ones override lower ones")
        b("Use the ZIP option for easy sharing — just send the .zip file!")

        text.config(state="disabled")

        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=8)

    # ─── ACTIONS ──────────────────────────────────────────────────────

    def _browse_output(self):
        d = filedialog.askdirectory(title="Where should the pack be saved?")
        if d:
            self.output_dir.set(d)

    def _choose_icon(self):
        f = filedialog.askopenfilename(
            title="Choose a 64x64 or 128x128 PNG as pack icon",
            filetypes=[("PNG files", "*.png")])
        if f:
            self.pack_icon_path = f
            self.icon_label.config(text=os.path.basename(f))

    def _on_edition_change(self, _event=None):
        edition = self.edition.get()
        self._java_ver_combo.pack_forget()
        self._bedrock_ver_combo.pack_forget()
        self._update_btn.pack_forget()
        if edition == "Java":
            self._java_ver_combo.pack(side=tk.LEFT)
        elif edition == "Bedrock":
            self._bedrock_ver_combo.pack(side=tk.LEFT)
        else:  # Both
            self._java_ver_combo.pack(side=tk.LEFT, padx=(0, 8))
            self._bedrock_ver_combo.pack(side=tk.LEFT)
        self._update_btn.pack(side=tk.LEFT, padx=(8, 0))

    # ─── VERSION UPDATE ──────────────────────────────────────────────

    def _merge_cached_versions(self):
        """Merge any previously cached versions into the Java combo."""
        cached = _load_version_cache()
        if not cached:
            return
        combined = dict(JAVA_PACK_FORMATS)
        for vid, fmt_info in cached.items():
            label = f"{vid} (fetched)"
            if label not in combined:
                combined[label] = fmt_info
        # Sort by format number descending so newest is first
        sorted_labels = sorted(combined.keys(),
                               key=lambda k: combined[k][0], reverse=True)
        self._java_ver_combo["values"] = sorted_labels
        # Store for pack generation lookup
        self._all_java_formats = combined

    def _check_for_new_versions(self):
        """Fetch new Java versions from Mojang API in a background thread."""
        self._update_btn.config(state="disabled", text="Checking...")
        self.status.set("Checking Mojang API for new versions...")

        def do_fetch():
            try:
                new_versions = _fetch_java_versions()
                self.root.after(0, lambda: self._apply_fetched_versions(new_versions))
            except Exception as e:
                self.root.after(0, lambda: self._fetch_failed(str(e)))

        threading.Thread(target=do_fetch, daemon=True).start()

    def _apply_fetched_versions(self, new_versions):
        """Called on main thread after fetch completes."""
        self._update_btn.config(state="normal", text="\u21bb Update Versions")

        if not new_versions:
            self.status.set("Versions are up to date!")
            messagebox.showinfo("Up to Date",
                "No new Minecraft versions found.\n"
                "Your version list is current.")
            return

        # Save to cache
        cached = _load_version_cache()
        cached.update(new_versions)
        _save_version_cache(cached)

        # Merge into active combo
        combined = dict(JAVA_PACK_FORMATS)
        for vid, fmt_info in cached.items():
            label = f"{vid} (fetched)"
            combined[label] = fmt_info
        sorted_labels = sorted(combined.keys(),
                               key=lambda k: combined[k][0], reverse=True)
        self._java_ver_combo["values"] = sorted_labels
        self._all_java_formats = combined

        # Auto-select the newest version
        if sorted_labels:
            self.java_version.set(sorted_labels[0])

        ver_list = ", ".join(new_versions.keys())
        self.status.set(f"Found {len(new_versions)} new version(s)!")
        messagebox.showinfo("Versions Updated",
            f"Found {len(new_versions)} new version(s):\n{ver_list}\n\n"
            "They've been added to the version picker.")

    def _fetch_failed(self, error_msg):
        """Called on main thread if fetch fails."""
        self._update_btn.config(state="normal", text="\u21bb Update Versions")
        self.status.set("Version check failed (offline?)")
        messagebox.showwarning("Update Failed",
            f"Couldn't reach Mojang API:\n{error_msg}\n\n"
            "Check your internet connection and try again.\n"
            "The hardcoded version list still works fine.")

    # ─── DRAG & DROP ──────────────────────────────────────────────────

    @staticmethod
    def _parse_dnd_paths(data):
        """Parse the raw string from tkinterdnd2 into a list of file paths.
        Paths with spaces are wrapped in {} by tkDnD."""
        paths = []
        raw = data.strip()
        i = 0
        while i < len(raw):
            if raw[i] == '{':
                j = raw.index('}', i)
                paths.append(raw[i + 1:j])
                i = j + 2  # skip } and space
            else:
                j = raw.find(' ', i)
                if j == -1:
                    paths.append(raw[i:])
                    break
                paths.append(raw[i:j])
                i = j + 1
        return [p for p in paths if p]

    def _handle_drop(self, event):
        """Handle files dropped onto the main treeview."""
        raw_paths = self._parse_dnd_paths(event.data)

        # Expand directories into their files
        all_files = []
        for p in raw_paths:
            if os.path.isdir(p):
                for root_dir, _, fnames in os.walk(p):
                    for fn in fnames:
                        all_files.append(os.path.join(root_dir, fn))
            elif os.path.isfile(p):
                all_files.append(p)

        if not all_files:
            return

        # Auto-classify files
        textures = [f for f in all_files
                    if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        models = [f for f in all_files
                  if f.lower().endswith(('.jem', '.json'))]
        properties = [f for f in all_files
                      if f.lower().endswith('.properties')]

        added = 0

        # Add textures as custom entity textures
        for tex in textures:
            tex_name = os.path.basename(tex)
            name_base = os.path.splitext(tex_name)[0]

            # Try to guess category from path
            lower_path = tex.lower().replace("\\", "/")
            if "/item/" in lower_path or "/items/" in lower_path:
                dest = f"assets/minecraft/textures/item/{tex_name}"
                category = "Item Texture"
            elif "/block/" in lower_path or "/blocks/" in lower_path:
                dest = f"assets/minecraft/textures/block/{tex_name}"
                category = "Block Texture"
            elif "/entity/" in lower_path:
                # Extract subfolder from original path
                idx = lower_path.index("/entity/") + len("/entity/")
                sub = tex.replace("\\", "/")[idx:]
                dest = f"assets/minecraft/textures/entity/{sub}"
                category = "Entity Texture"
            else:
                dest = f"assets/minecraft/textures/entity/{tex_name}"
                category = "Entity Texture"

            entry = {
                "source_file": tex,
                "dest_path": dest,
                "display_name": tex_name,
                "category": category,
            }
            self.entries.append(entry)
            self.tree.insert("", "end",
                values=(tex_name, os.path.basename(tex), category))
            added += 1

        # Add models
        for mdl in models:
            mdl_name = os.path.basename(mdl)
            ext = os.path.splitext(mdl_name)[1].lower()

            lower_path = mdl.lower().replace("\\", "/")
            if ext == ".jem" or "/cem/" in lower_path:
                dest = f"assets/minecraft/optifine/cem/{mdl_name}"
                category = "CEM Model"
            elif "/item/" in lower_path:
                dest = f"assets/minecraft/models/item/{mdl_name}"
                category = "Item Model"
            elif "/block/" in lower_path:
                dest = f"assets/minecraft/models/block/{mdl_name}"
                category = "Block Model"
            else:
                dest = f"assets/minecraft/optifine/cem/{mdl_name}"
                category = "CEM Model"

            entry = {
                "source_file": mdl,
                "dest_path": dest,
                "display_name": mdl_name,
                "category": category,
            }
            self.entries.append(entry)
            self.tree.insert("", "end",
                values=(mdl_name, os.path.basename(mdl), category))
            added += 1

        # Add properties files
        for prop in properties:
            prop_name = os.path.basename(prop)
            lower_path = prop.lower().replace("\\", "/")
            if "emissive" in prop_name.lower():
                dest = f"assets/minecraft/optifine/{prop_name}"
                category = "OptiFine Config"
            elif "/cem/" in lower_path:
                dest = f"assets/minecraft/optifine/cem/{prop_name}"
                category = "Random Entity Config"
            elif "/random/" in lower_path:
                # Preserve subpath after random/
                idx = lower_path.index("/random/") + len("/random/")
                sub = prop.replace("\\", "/")[idx:]
                dest = f"assets/minecraft/optifine/random/{sub}"
                category = "Random Entity Config"
            else:
                dest = f"assets/minecraft/optifine/{prop_name}"
                category = "OptiFine Config"

            entry = {
                "source_file": prop,
                "dest_path": dest,
                "display_name": prop_name,
                "category": category,
            }
            self.entries.append(entry)
            self.tree.insert("", "end",
                values=(prop_name, os.path.basename(prop), category))
            added += 1

        self._update_status()
        if added:
            self.status.set(
                f"Dropped {added} file(s): "
                f"{len(textures)} texture(s), {len(models)} model(s), "
                f"{len(properties)} config(s)")

    # ─── WIZARD: "Replace a Texture" ─────────────────────────────────

    def _wizard_replace(self):
        """Main user-facing wizard: pick category -> pick asset -> pick your file."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Replace a Texture")
        dlg.geometry("620x520")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Step 1: What do you want to retexture?",
                  font=("Segoe UI", 11, "bold")).pack(pady=(10, 5))

        # Category selector
        cat_frame = ttk.Frame(dlg)
        cat_frame.pack(fill="x", padx=15)
        ttk.Label(cat_frame, text="Category:").pack(side=tk.LEFT)
        cat_var = tk.StringVar(value=list(ASSET_CATEGORIES.keys())[0])
        cat_combo = ttk.Combobox(cat_frame, textvariable=cat_var,
                                 values=list(ASSET_CATEGORIES.keys()),
                                 state="readonly", width=22)
        cat_combo.pack(side=tk.LEFT, padx=8)

        # Search
        ttk.Label(cat_frame, text="Search:").pack(side=tk.LEFT, padx=(15, 0))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(cat_frame, textvariable=search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(dlg, text="Step 2: Pick the specific block / item / mob:",
                  font=("Segoe UI", 11, "bold")).pack(pady=(12, 5))

        # Asset listbox
        lb_frame = ttk.Frame(dlg)
        lb_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self._wiz_listbox = tk.Listbox(lb_frame, font=("Segoe UI", 10))
        lb_scroll = ttk.Scrollbar(lb_frame, orient="vertical",
                                  command=self._wiz_listbox.yview)
        self._wiz_listbox.configure(yscrollcommand=lb_scroll.set)
        self._wiz_listbox.pack(side=tk.LEFT, fill="both", expand=True)
        lb_scroll.pack(side=tk.RIGHT, fill="y")

        def refresh_list(*_):
            assets_dict, _ = ASSET_CATEGORIES[cat_var.get()]
            query = search_var.get().lower()
            self._wiz_listbox.delete(0, tk.END)
            for name in sorted(assets_dict.keys()):
                if query in name.lower():
                    self._wiz_listbox.insert(tk.END, name)

        cat_combo.bind("<<ComboboxSelected>>", refresh_list)
        search_var.trace_add("write", refresh_list)
        refresh_list()

        ttk.Label(dlg, text="Step 3: Choose your replacement image file (PNG recommended):",
                  font=("Segoe UI", 11, "bold")).pack(pady=(10, 5))

        file_frame = ttk.Frame(dlg)
        file_frame.pack(fill="x", padx=15)
        chosen_file = tk.StringVar(value="(no file chosen)")
        ttk.Label(file_frame, textvariable=chosen_file,
                  width=50).pack(side=tk.LEFT, fill="x", expand=True)

        def pick_file():
            f = filedialog.askopenfilename(
                title="Choose your replacement texture",
                filetypes=[("Image files", "*.png *.jpg *.jpeg"),
                           ("All files", "*.*")])
            if f:
                chosen_file.set(f)

        ttk.Button(file_frame, text="Browse...", command=pick_file).pack(side=tk.LEFT, padx=5)

        def add_and_close():
            sel = self._wiz_listbox.curselection()
            if not sel:
                messagebox.showwarning("Select Something",
                    "Please select what you want to retexture from the list.",
                    parent=dlg)
                return
            src = chosen_file.get()
            if not src or src == "(no file chosen)" or not os.path.isfile(src):
                messagebox.showwarning("Choose a File",
                    "Please choose your replacement image file.",
                    parent=dlg)
                return

            asset_name = self._wiz_listbox.get(sel[0])
            cat_name = cat_var.get()
            assets_dict, base_folder = ASSET_CATEGORIES[cat_name]
            mc_filename = assets_dict[asset_name]

            # Build dest path — Minecraft requires exact filename + .png
            dest = f"{base_folder}/{mc_filename}.png"

            # Check for duplicate
            for e in self.entries:
                if e["dest_path"] == dest:
                    messagebox.showinfo("Already Added",
                        f"You already have a replacement for '{asset_name}'.\n"
                        "Remove it first if you want to change it.",
                        parent=dlg)
                    return

            entry = {
                "source_file": src,
                "dest_path": dest,
                "display_name": asset_name,
                "category": cat_name,
            }
            self.entries.append(entry)
            self.tree.insert("", "end",
                values=(asset_name, os.path.basename(src), cat_name))
            self._update_status()
            dlg.destroy()

        ttk.Button(dlg, text="Add Replacement", command=add_and_close,
                   style="Action.TButton").pack(pady=12)

    # ─── ADD CUSTOM MODEL WIZARD ─────────────────────────────────────

    def _wizard_add_model(self):
        """Guided wizard for adding custom models — select all files at once,
        the tool auto-classifies models vs textures by extension and name."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Custom Model")
        dlg.geometry("640x480")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Add a Custom Model",
                  font=("Segoe UI", 12, "bold")).pack(pady=(12, 4))
        ttk.Label(dlg, text=(
            "Select ALL your files at once — model (.jem/.json) and textures (.png).\n"
            "The tool will automatically figure out which is the model and which are textures."),
                  font=("Segoe UI", 9), justify="center").pack(pady=(0, 12))

        # File selection
        file_frame = ttk.LabelFrame(dlg, text="Your Files", padding=10)
        file_frame.pack(fill="x", padx=20, pady=(0, 10))

        all_files = []
        file_summary = tk.StringVar(value="No files selected")

        def pick_files():
            files = filedialog.askopenfilenames(
                title="Select model + texture files",
                filetypes=[("Model & Texture files", "*.jem *.json *.png *.jpg *.jpeg"),
                           ("All files", "*.*")])
            if files:
                all_files.clear()
                all_files.extend(files)
                models = [f for f in files
                          if f.lower().endswith(('.jem', '.json'))]
                textures = [f for f in files
                            if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                file_summary.set(
                    f"{len(models)} model(s), {len(textures)} texture(s) selected")
                # Auto-detect entity name from the model file
                if models:
                    name = os.path.splitext(os.path.basename(models[0]))[0]
                    entity_name.set(name)

        summary_lbl = ttk.Label(file_frame, textvariable=file_summary)
        summary_lbl.pack(side=tk.LEFT, fill="x", expand=True)
        ttk.Button(file_frame, text="Browse...", command=pick_files).pack(
            side=tk.LEFT, padx=5)

        # Drag & drop onto file area
        if HAS_DND:
            def _drop_model_files(event):
                paths = self._parse_dnd_paths(event.data)
                expanded = []
                for p in paths:
                    if os.path.isdir(p):
                        for rd, _, fns in os.walk(p):
                            expanded.extend(os.path.join(rd, fn) for fn in fns)
                    elif os.path.isfile(p):
                        expanded.append(p)
                if expanded:
                    all_files.clear()
                    all_files.extend(expanded)
                    mdls = [f for f in expanded
                            if f.lower().endswith(('.jem', '.json'))]
                    texs = [f for f in expanded
                            if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    file_summary.set(
                        f"{len(mdls)} model(s), {len(texs)} texture(s) selected")
                    if mdls:
                        nm = os.path.splitext(os.path.basename(mdls[0]))[0]
                        entity_name.set(nm)
                    if any(f.lower().endswith('.jem') for f in expanded):
                        model_type.set("cem")
                    update_preview()
            for w in (summary_lbl, file_frame):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", _drop_model_files)
            file_summary.set("No files selected — browse or drag & drop")

        # Model type (auto-detected from .jem, but user can override)
        type_frame = ttk.LabelFrame(dlg, text="Model Type", padding=10)
        type_frame.pack(fill="x", padx=20, pady=(0, 10))

        model_type = tk.StringVar(value="cem")
        type_row = ttk.Frame(type_frame)
        type_row.pack(fill="x")
        ttk.Radiobutton(type_row, text="Entity (CEM/JEM — OptiFine)",
                        variable=model_type, value="cem").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(type_row, text="Item Model",
                        variable=model_type, value="item").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(type_row, text="Block Model",
                        variable=model_type, value="block").pack(side=tk.LEFT)

        ttk.Label(type_frame, text=(
            "Tip: .jem files are always Entity (CEM). For .json files, pick the correct type."),
                  font=("Segoe UI", 8)).pack(anchor="w", pady=(5, 0))

        # Name field
        name_frame = ttk.LabelFrame(dlg, text="Entity / Model Name", padding=10)
        name_frame.pack(fill="x", padx=20, pady=(0, 10))

        entity_name = tk.StringVar(value="")
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        ttk.Entry(name_frame, textvariable=entity_name, width=25).pack(
            side=tk.LEFT, padx=5)
        ttk.Label(name_frame, text="(auto-filled from model filename)",
                  font=("Segoe UI", 8)).pack(side=tk.LEFT)

        # Preview of what will happen
        preview_frame = ttk.LabelFrame(dlg, text="What will be added", padding=10)
        preview_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        preview_text = tk.Text(preview_frame, height=6, width=70, state="disabled",
                               font=("Consolas", 9), wrap="word")
        preview_text.pack(fill="both", expand=True)

        def update_preview(*_):
            name = entity_name.get().strip() or "(name)"
            mtype = model_type.get()
            lines = []
            models = [f for f in all_files if f.lower().endswith(('.jem', '.json'))]
            textures = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

            for m in models:
                ext = os.path.splitext(m)[1].lower()
                if mtype == "cem":
                    dest_ext = ext if ext in (".jem", ".json") else ".jem"
                    lines.append(f"  Model → optifine/cem/{name}{dest_ext}")
                elif mtype == "item":
                    lines.append(f"  Model → models/item/{name}.json")
                else:
                    lines.append(f"  Model → models/block/{name}.json")

            for t in textures:
                tname = os.path.basename(t)
                if mtype == "cem":
                    lines.append(f"  Texture → textures/entity/{name}/{tname}")
                elif mtype == "item":
                    lines.append(f"  Texture → textures/item/{tname}")
                else:
                    lines.append(f"  Texture → textures/block/{tname}")

            preview_text.config(state="normal")
            preview_text.delete("1.0", "end")
            preview_text.insert("1.0", "\n".join(lines) if lines else "(select files first)")
            preview_text.config(state="disabled")

        entity_name.trace_add("write", update_preview)
        model_type.trace_add("write", update_preview)

        # Override pick_files to also update preview
        orig_pick = pick_files

        def pick_and_preview():
            orig_pick()
            # Auto-set type to CEM if .jem file detected
            if any(f.lower().endswith('.jem') for f in all_files):
                model_type.set("cem")
            update_preview()

        file_frame.winfo_children()[-1].config(command=pick_and_preview)

        # Add button
        def add_all():
            if not all_files:
                messagebox.showwarning("No Files",
                    "Please select your model and texture files.", parent=dlg)
                return
            name = entity_name.get().strip()
            if not name:
                messagebox.showwarning("No Name",
                    "Please enter a name for the model/entity.", parent=dlg)
                return

            mtype = model_type.get()
            models = [f for f in all_files if f.lower().endswith(('.jem', '.json'))]
            textures = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            added = 0

            # Add model file(s)
            for src in models:
                ext = os.path.splitext(src)[1].lower()
                if mtype == "cem":
                    dest_ext = ext if ext in (".jem", ".json") else ".jem"
                    dest = f"assets/minecraft/optifine/cem/{name}{dest_ext}"
                    category = "CEM Model"
                elif mtype == "item":
                    dest = f"assets/minecraft/models/item/{name}.json"
                    category = "Item Model"
                else:
                    dest = f"assets/minecraft/models/block/{name}.json"
                    category = "Block Model"

                entry = {
                    "source_file": src,
                    "dest_path": dest,
                    "display_name": os.path.basename(dest),
                    "category": category,
                }
                self.entries.append(entry)
                self.tree.insert("", "end",
                    values=(os.path.basename(dest), os.path.basename(src), category))
                added += 1

            # Add texture files
            for tex in textures:
                tex_name = os.path.basename(tex)
                if mtype == "cem":
                    tex_dest = f"assets/minecraft/textures/entity/{name}/{tex_name}"
                    category = "Entity Texture"
                    display = f"{name}/{tex_name}"
                elif mtype == "item":
                    tex_dest = f"assets/minecraft/textures/item/{tex_name}"
                    category = "Item Texture"
                    display = tex_name
                else:
                    tex_dest = f"assets/minecraft/textures/block/{tex_name}"
                    category = "Block Texture"
                    display = tex_name

                entry = {
                    "source_file": tex,
                    "dest_path": tex_dest,
                    "display_name": tex_name,
                    "category": category,
                }
                self.entries.append(entry)
                self.tree.insert("", "end",
                    values=(display, os.path.basename(tex), category))
                added += 1

            self._update_status()
            messagebox.showinfo("Added",
                f"Added {added} file(s) to pack!\n\n"
                f"• {len(models)} model(s)\n"
                f"• {len(textures)} texture(s)\n\n"
                "All paths set automatically.",
                parent=dlg)
            dlg.destroy()

        ttk.Button(dlg, text="Add to Pack", command=add_all,
                   style="Action.TButton").pack(pady=10)

    # ─── RANDOM MOB SKINS WIZARD ─────────────────────────────────────

    # Known entity names for the dropdown
    ENTITY_NAMES = [
        "allay", "axolotl", "bat", "bee", "blaze", "camel", "cat", "cave_spider",
        "chicken", "cod", "cow", "creeper", "dolphin", "donkey", "drowned",
        "elder_guardian", "ender_dragon", "enderman", "endermite", "evoker",
        "fox", "frog", "ghast", "glow_squid", "goat", "guardian", "hoglin",
        "horse", "husk", "iron_golem", "llama", "magma_cube", "mooshroom",
        "mule", "ocelot", "panda", "parrot", "phantom", "pig", "piglin",
        "piglin_brute", "pillager", "polar_bear", "pufferfish", "rabbit",
        "ravager", "salmon", "sheep", "shulker", "silverfish", "skeleton",
        "skeleton_horse", "slime", "sniffer", "snow_golem", "spider", "squid",
        "stray", "strider", "tadpole", "tropical_fish", "turtle", "vex",
        "villager", "vindicator", "wandering_trader", "warden", "witch",
        "wither", "wither_skeleton", "wolf", "zoglin", "zombie",
        "zombie_horse", "zombie_villager", "zombified_piglin",
    ]

    def _wizard_random_entity(self):
        """Wizard for setting up multiple random skins for an entity.
        Supports: random spawn weights, random models, and nametag-triggered skins."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Random Mob Skins")
        dlg.geometry("760x700")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Multi-Skin Setup",
                  font=("Segoe UI", 13, "bold")).pack(pady=(10, 2))
        ttk.Label(dlg, text="Give a mob multiple looks — random, by nametag, or both.",
                  font=("Segoe UI", 9)).pack(pady=(0, 8))

        # ── Top row: Entity + Method side by side
        top_row = ttk.Frame(dlg)
        top_row.pack(fill="x", padx=16, pady=(0, 6))

        ent_frame = ttk.LabelFrame(top_row, text="Which mob?", padding=6)
        ent_frame.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 6))

        entity_name = tk.StringVar(value="")
        ent_combo = ttk.Combobox(ent_frame, textvariable=entity_name,
                                 values=self.ENTITY_NAMES, width=18)
        ent_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(ent_frame, text="type or pick",
                  font=("Segoe UI", 8), foreground="#888").pack(side=tk.LEFT)

        method_frame = ttk.LabelFrame(top_row, text="How?", padding=6)
        method_frame.pack(side=tk.LEFT, fill="x", expand=True)

        method = tk.StringVar(value="random")
        methods = [
            ("Random Skins", "random",
             "Same shape, different textures — picked at random"),
            ("Random Models", "random_models",
             "Different 3D shapes — each with its own texture"),
            ("Nametag", "nametag",
             "Skin changes when you name a mob"),
            ("Mixed", "both",
             "Some random + some nametag-triggered"),
        ]
        for label, val, tip in methods:
            ttk.Radiobutton(method_frame, text=label,
                            variable=method, value=val).pack(side=tk.LEFT, padx=4)

        # Method description label
        method_desc_var = tk.StringVar(value=methods[0][2])
        method_desc_lbl = ttk.Label(dlg, textvariable=method_desc_var,
                                    font=("Segoe UI", 8), foreground="#666")
        method_desc_lbl.pack(pady=(0, 4))

        def on_method_change(*_):
            m = method.get()
            for _, val, tip in methods:
                if val == m:
                    method_desc_var.set(tip)
                    break
            _rebuild_skin_rows()
        method.trace_add("write", on_method_change)

        # ── Skin entries area
        skins_outer = ttk.LabelFrame(dlg, text="Variants", padding=6)
        skins_outer.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        # Column headers (rebuilt when method changes)
        header_frame = ttk.Frame(skins_outer)
        header_frame.pack(fill="x")

        # Scrollable area
        canvas = tk.Canvas(skins_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(skins_outer, orient="vertical", command=canvas.yview)
        skin_list_frame = ttk.Frame(canvas)

        skin_list_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=skin_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # Mouse wheel scroll
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        canvas.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        skin_entries = []  # List of dicts

        def _rebuild_skin_rows():
            """Rebuild column headers and update row visibility for method."""
            m = method.get()
            # Clear header
            for w in header_frame.winfo_children():
                w.destroy()
            # Build header labels based on method
            ttk.Label(header_frame, text="#", width=3,
                      font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
            ttk.Label(header_frame, text="Texture (.png)", width=30,
                      font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=2)
            if m in ("random_models", "both"):
                ttk.Label(header_frame, text="Model (.jem)", width=22,
                          font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=2)
            if m in ("random", "random_models", "both"):
                ttk.Label(header_frame, text="Weight", width=6,
                          font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=2)
            if m in ("nametag", "both"):
                ttk.Label(header_frame, text="Nametag", width=14,
                          font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=2)
            # Show/hide widgets in existing rows
            for sd in skin_entries:
                _update_row_visibility(sd, m)

        def _update_row_visibility(sd, m):
            """Show/hide model, weight, nametag widgets based on method."""
            if m in ("random_models", "both"):
                sd["mdl_entry"].pack(side=tk.LEFT, padx=2, after=sd["tex_btn"])
                sd["mdl_btn"].pack(side=tk.LEFT, after=sd["mdl_entry"])
            else:
                sd["mdl_entry"].pack_forget()
                sd["mdl_btn"].pack_forget()
            if m in ("random", "random_models", "both"):
                sd["wt_lbl"].pack(side=tk.LEFT, padx=(4, 0),
                                  after=sd.get("mdl_btn") or sd["tex_btn"])
                sd["wt_entry"].pack(side=tk.LEFT, after=sd["wt_lbl"])
            else:
                sd["wt_lbl"].pack_forget()
                sd["wt_entry"].pack_forget()
            if m in ("nametag", "both"):
                sd["nm_lbl"].pack(side=tk.LEFT, padx=(4, 0))
                sd["nm_entry"].pack(side=tk.LEFT, after=sd["nm_lbl"])
            else:
                sd["nm_lbl"].pack_forget()
                sd["nm_entry"].pack_forget()

        def add_skin_row(texture_path="", model_path="", weight="10", nametag=""):
            row_idx = len(skin_entries)
            row = ttk.Frame(skin_list_frame)
            row.pack(fill="x", pady=2)

            sd = {
                "texture": tk.StringVar(value=texture_path),
                "model": tk.StringVar(value=model_path),
                "weight": tk.StringVar(value=weight),
                "nametag": tk.StringVar(value=nametag),
                "frame": row,
            }

            ttk.Label(row, text=f"#{row_idx + 1}", width=3).pack(side=tk.LEFT)

            # Texture
            tex_entry = ttk.Entry(row, textvariable=sd["texture"], width=30)
            tex_entry.pack(side=tk.LEFT, padx=2)
            def pick_tex(sv=sd["texture"]):
                f = filedialog.askopenfilename(
                    title=f"Variant #{row_idx + 1} texture",
                    filetypes=[("PNG", "*.png"), ("All", "*.*")],
                    parent=dlg)
                if f:
                    sv.set(f)
            tex_btn = ttk.Button(row, text="...", command=pick_tex, width=3)
            tex_btn.pack(side=tk.LEFT)
            sd["tex_btn"] = tex_btn

            # Model
            mdl_entry = ttk.Entry(row, textvariable=sd["model"], width=22)
            def pick_mdl(sv=sd["model"]):
                f = filedialog.askopenfilename(
                    title=f"Variant #{row_idx + 1} model",
                    filetypes=[("Model", "*.jem *.json"), ("All", "*.*")],
                    parent=dlg)
                if f:
                    sv.set(f)
            mdl_btn = ttk.Button(row, text="...", command=pick_mdl, width=3)
            sd["mdl_entry"] = mdl_entry
            sd["mdl_btn"] = mdl_btn

            # Weight
            wt_lbl = ttk.Label(row, text="W:")
            wt_entry = ttk.Entry(row, textvariable=sd["weight"], width=4)
            sd["wt_lbl"] = wt_lbl
            sd["wt_entry"] = wt_entry

            # Nametag
            nm_lbl = ttk.Label(row, text="Name:")
            nm_entry = ttk.Entry(row, textvariable=sd["nametag"], width=14)
            sd["nm_lbl"] = nm_lbl
            sd["nm_entry"] = nm_entry

            skin_entries.append(sd)

            # Drag & drop on the texture entry
            if HAS_DND:
                def _drop_on_tex(event, sv_tex=sd["texture"], sv_mdl=sd["model"]):
                    paths = self._parse_dnd_paths(event.data)
                    for p in paths:
                        if p.lower().endswith(('.png', '.jpg', '.jpeg')):
                            sv_tex.set(p)
                        elif p.lower().endswith(('.jem', '.json')):
                            sv_mdl.set(p)
                tex_entry.drop_target_register(DND_FILES)
                tex_entry.dnd_bind("<<Drop>>", _drop_on_tex)
                mdl_entry.drop_target_register(DND_FILES)
                mdl_entry.dnd_bind("<<Drop>>",
                    lambda e, sv=sd["model"]: sv.set(
                        self._parse_dnd_paths(e.data)[0]
                        if self._parse_dnd_paths(e.data) else ""))

            # Apply current method visibility
            _update_row_visibility(sd, method.get())

        # Start with 2 rows
        add_skin_row()
        add_skin_row()
        _rebuild_skin_rows()

        # Bottom controls
        ctrl_frame = ttk.Frame(skins_outer)
        ctrl_frame.pack(fill="x", pady=(4, 0))
        ttk.Button(ctrl_frame, text="+ Add Variant",
                   command=lambda: (add_skin_row(),
                                    _update_row_visibility(skin_entries[-1],
                                                           method.get()))
                   ).pack(side=tk.LEFT)
        if HAS_DND:
            ttk.Label(ctrl_frame, text="  (or drag & drop files onto the fields)",
                      font=("Segoe UI", 8), foreground="#888").pack(side=tk.LEFT)

        # ── Include models checkbox
        include_models = tk.BooleanVar(value=True)
        ttk.Checkbutton(dlg, text="Include .jem models (if provided)",
                        variable=include_models).pack(anchor="w", padx=16)

        # ── Generate button
        def generate():
            name = entity_name.get().strip()
            if not name:
                messagebox.showwarning("No Entity",
                    "Please select or type an entity name.", parent=dlg)
                return

            # Validate skins
            valid_skins = []
            for i, sd in enumerate(skin_entries):
                tex = sd["texture"].get().strip()
                if not tex or not os.path.isfile(tex):
                    continue
                valid_skins.append({
                    "texture": tex,
                    "model": sd["model"].get().strip(),
                    "weight": sd["weight"].get().strip() or "10",
                    "nametag": sd["nametag"].get().strip(),
                    "index": i,
                })

            if len(valid_skins) < 2:
                messagebox.showwarning("Need More Skins",
                    "Please add at least 2 variants with valid texture files.",
                    parent=dlg)
                return

            m = method.get()
            added = 0

            # For "random_models" mode, every variant needs a model
            if m == "random_models":
                missing_models = [i + 1 for i, s in enumerate(valid_skins)
                                  if not s["model"] or not os.path.isfile(s["model"])]
                if missing_models:
                    messagebox.showwarning("Models Required",
                        f"Random Models requires a .jem for every variant.\n\n"
                        f"Missing: {', '.join(f'#{n}' for n in missing_models)}",
                        parent=dlg)
                    return

            # ── Add texture files
            for i, skin in enumerate(valid_skins):
                if i == 0:
                    tex_filename = f"{name}.png"
                else:
                    tex_filename = f"{name}{i + 1}.png"

                tex_dest = f"assets/minecraft/textures/entity/{name}/{tex_filename}"
                entry = {
                    "source_file": skin["texture"],
                    "dest_path": tex_dest,
                    "display_name": tex_filename,
                    "category": "Entity Texture",
                }
                self.entries.append(entry)
                self.tree.insert("", "end",
                    values=(f"{name}/{tex_filename}",
                            os.path.basename(skin["texture"]),
                            "Entity Texture"))
                added += 1

                # Check for emissive variant (_e suffix)
                tex_dir = os.path.dirname(skin["texture"])
                tex_base = os.path.splitext(os.path.basename(skin["texture"]))[0]
                emissive_src = os.path.join(tex_dir, f"{tex_base}_e.png")
                if os.path.isfile(emissive_src):
                    if i == 0:
                        e_filename = f"{name}_e.png"
                    else:
                        e_filename = f"{name}{i + 1}_e.png"
                    e_dest = f"assets/minecraft/textures/entity/{name}/{e_filename}"
                    entry = {
                        "source_file": emissive_src,
                        "dest_path": e_dest,
                        "display_name": e_filename,
                        "category": "Entity Texture (Emissive)",
                    }
                    self.entries.append(entry)
                    self.tree.insert("", "end",
                        values=(f"{name}/{e_filename}",
                                os.path.basename(emissive_src),
                                "Entity Texture (Emissive)"))
                    added += 1

            # ── Add model files
            has_models = False
            should_include = include_models.get() or m == "random_models"
            if should_include:
                for i, skin in enumerate(valid_skins):
                    mdl = skin["model"]
                    if mdl and os.path.isfile(mdl):
                        has_models = True
                        ext = os.path.splitext(mdl)[1].lower()
                        dest_ext = ext if ext in (".jem", ".json") else ".jem"
                        if i == 0:
                            mdl_filename = f"{name}{dest_ext}"
                        else:
                            mdl_filename = f"{name}{i + 1}{dest_ext}"
                        mdl_dest = f"assets/minecraft/optifine/cem/{mdl_filename}"
                        entry = {
                            "source_file": mdl,
                            "dest_path": mdl_dest,
                            "display_name": mdl_filename,
                            "category": "CEM Model",
                        }
                        self.entries.append(entry)
                        self.tree.insert("", "end",
                            values=(mdl_filename, os.path.basename(mdl), "CEM Model"))
                        added += 1

            # ── Generate .properties file
            props_lines = [f"# {name}.properties\n"]

            if m == "random_models":
                indices = " ".join(str(i + 1) for i in range(len(valid_skins)))
                weights = " ".join(s["weight"] for s in valid_skins)
                props_lines.append(f"models.1={indices}\n")
                props_lines.append(f"weights.1={weights}\n")

            elif m == "random" or m == "both":
                random_skins = [s for s in valid_skins
                                if m == "random" or not s["nametag"]]
                if random_skins:
                    indices = " ".join(str(i + 1) for i in range(len(random_skins)))
                    weights = " ".join(s["weight"] for s in random_skins)
                    if has_models:
                        props_lines.append(f"models.1={indices}\n")
                    else:
                        props_lines.append(f"textures.1={indices}\n")
                    props_lines.append(f"weights.1={weights}\n")

            if m == "nametag" or m == "both":
                rule_n = 2 if m == "both" else 1
                for skin in valid_skins:
                    if skin["nametag"]:
                        idx = valid_skins.index(skin) + 1
                        if has_models:
                            props_lines.append(f"models.{rule_n}={idx}\n")
                        else:
                            props_lines.append(f"textures.{rule_n}={idx}\n")
                        props_lines.append(f"name.{rule_n}={skin['nametag']}\n")
                        rule_n += 1

            props_content = "".join(props_lines)
            props_tmp = os.path.join(tempfile.gettempdir(),
                                     f"{name}_random.properties")
            with open(props_tmp, "w") as f:
                f.write(props_content)

            if has_models or m == "random_models":
                props_dest = f"assets/minecraft/optifine/cem/{name}.properties"
            else:
                props_dest = f"assets/minecraft/optifine/random/entity/{name}/{name}.properties"

            entry = {
                "source_file": props_tmp,
                "dest_path": props_dest,
                "display_name": f"{name}.properties",
                "category": "Random Entity Config",
            }
            self.entries.append(entry)
            self.tree.insert("", "end",
                values=(f"{name}.properties", "(auto-generated)",
                        "Random Entity Config"))
            added += 1

            # ── Generate emissive.properties if needed
            has_emissive = any("_e.png" in e.get("dest_path", "")
                              for e in self.entries)
            if has_emissive:
                emissive_tmp = os.path.join(tempfile.gettempdir(),
                                           "emissive.properties")
                with open(emissive_tmp, "w") as f:
                    f.write("suffix.emissive=_e\n")
                entry = {
                    "source_file": emissive_tmp,
                    "dest_path": "assets/minecraft/optifine/emissive.properties",
                    "display_name": "emissive.properties",
                    "category": "OptiFine Config",
                }
                self.entries.append(entry)
                self.tree.insert("", "end",
                    values=("emissive.properties", "(auto-generated)",
                            "OptiFine Config"))
                added += 1

            self._update_status()
            method_label = {
                "random": "Random Skins",
                "random_models": "Random Models",
                "nametag": "Nametag",
                "both": "Mixed",
            }.get(m, m)
            messagebox.showinfo("Done!",
                f"Added {added} file(s) for {name}!\n\n"
                f"{len(valid_skins)} variant(s) \u2022 {method_label}\n"
                f"Properties file auto-generated.",
                parent=dlg)
            dlg.destroy()

        ttk.Button(dlg, text="Generate & Add to Pack", command=generate,
                   style="Big.TButton").pack(pady=8)

    # ─── ADD CUSTOM FILE (advanced) ───────────────────────────────────

    def _add_custom_file(self):
        """For advanced users: add any file (model JSON, properties, etc.)
        with a guided path picker."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Custom File")
        dlg.geometry("550x320")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Choose your file:",
                  font=("Segoe UI", 10, "bold")).pack(pady=(10, 5))
        file_var = tk.StringVar(value="(no file chosen)")
        ff = ttk.Frame(dlg)
        ff.pack(fill="x", padx=15)
        ttk.Label(ff, textvariable=file_var, width=50).pack(side=tk.LEFT, fill="x", expand=True)

        def pick():
            f = filedialog.askopenfilename(
                title="Choose file",
                filetypes=[("All supported", "*.png *.jpg *.jpeg *.json *.jem *.properties"),
                           ("All files", "*.*")])
            if f:
                file_var.set(f)
                # Auto-detect type and suggest a path
                ext = os.path.splitext(f)[1].lower()
                if ext == '.json':
                    try:
                        with open(f, 'r', encoding='utf-8') as fh:
                            data = json.load(fh)
                        if "variants" in data or "multipart" in data:
                            path_var.set(f"assets/minecraft/blockstates/{os.path.basename(f)}")
                        elif "parent" in data and "item/" in data.get("parent", ""):
                            path_var.set(f"assets/minecraft/models/item/{os.path.basename(f)}")
                        elif "parent" in data and "block/" in data.get("parent", ""):
                            path_var.set(f"assets/minecraft/models/block/{os.path.basename(f)}")
                        else:
                            path_var.set(f"assets/minecraft/models/item/{os.path.basename(f)}")
                    except Exception:
                        path_var.set(f"assets/minecraft/{os.path.basename(f)}")
                elif ext == '.jem':
                    path_var.set(f"assets/minecraft/optifine/cem/{os.path.basename(f)}")
                elif ext == '.properties':
                    path_var.set(f"assets/minecraft/optifine/cit/{os.path.basename(f)}")
                else:
                    path_var.set(f"assets/minecraft/textures/block/{os.path.basename(f)}")

        ttk.Button(ff, text="Browse...", command=pick).pack(side=tk.LEFT, padx=5)

        ttk.Label(dlg, text="Destination path inside the pack:",
                  font=("Segoe UI", 10, "bold")).pack(pady=(15, 5))
        path_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=path_var, width=65).pack(padx=15)

        ttk.Label(dlg, text="Quick presets:",
                  font=("Segoe UI", 9)).pack(pady=(10, 3))
        presets = ttk.Frame(dlg)
        presets.pack()
        for label, base in [
            ("Block Texture", "assets/minecraft/textures/block"),
            ("Item Texture", "assets/minecraft/textures/item"),
            ("Item Model", "assets/minecraft/models/item"),
            ("Block Model", "assets/minecraft/models/block"),
            ("Blockstate", "assets/minecraft/blockstates"),
            ("CIT (OptiFine)", "assets/minecraft/optifine/cit"),
            ("CEM (OptiFine)", "assets/minecraft/optifine/cem"),
        ]:
            def _set(b=base):
                src = file_var.get()
                fn = os.path.basename(src) if os.path.isfile(src) else "file.png"
                path_var.set(f"{b}/{fn}")
            ttk.Button(presets, text=label, command=_set).pack(side=tk.LEFT, padx=2)

        def add():
            src = file_var.get()
            dest = path_var.get().strip()
            if not src or not os.path.isfile(src):
                messagebox.showwarning("No File", "Please choose a file.", parent=dlg)
                return
            if not dest:
                messagebox.showwarning("No Path", "Please set a destination path.", parent=dlg)
                return
            entry = {
                "source_file": src,
                "dest_path": dest,
                "display_name": os.path.basename(dest),
                "category": "Custom",
            }
            self.entries.append(entry)
            self.tree.insert("", "end",
                values=(os.path.basename(dest), os.path.basename(src), "Custom"))
            self._update_status()
            dlg.destroy()

        ttk.Button(dlg, text="Add to Pack", command=add,
                   style="Action.TButton").pack(pady=15)

    # ─── LIST MANAGEMENT ──────────────────────────────────────────────

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        indices = []
        for item_id in sel:
            idx = self.tree.index(item_id)
            indices.append(idx)
            self.tree.delete(item_id)
        for i in sorted(indices, reverse=True):
            if i < len(self.entries):
                self.entries.pop(i)
        self._update_status()

    def _clear_all(self):
        if not self.entries:
            return
        if messagebox.askyesno("Confirm", "Remove all texture replacements?"):
            self.entries.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._update_status()

    def _update_status(self):
        n = len(self.entries)
        if n == 0:
            self.status.set("Ready — click 'Replace a Texture...' to start")
        else:
            self.status.set(f"{n} texture replacement(s) queued")

    # ─── PACK GENERATION ──────────────────────────────────────────────

    def _generate_pack(self):
        name = self.pack_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a pack name.")
            return
        if not self.entries:
            messagebox.showerror("Error",
                "No textures added yet.\n\n"
                "Click 'Replace a Texture...' to add your first replacement.")
            return

        out = self.output_dir.get()
        if not out:
            out = filedialog.askdirectory(title="Where should the pack be saved?")
            if not out:
                return
            self.output_dir.set(out)

        edition = self.edition.get()
        results = []

        try:
            if edition in ("Java", "Both (Java + Bedrock)"):
                r = self._generate_java_pack(name, out)
                results.append(("Java Edition", r))

            if edition in ("Bedrock", "Both (Java + Bedrock)"):
                r = self._generate_bedrock_pack(name, out)
                results.append(("Bedrock Edition", r))

            # Build result message
            msg_parts = []
            for label, r in results:
                msg_parts.append(f"── {label} ──")
                msg_parts.append(f"Folder: {r['folder']}")
                if r.get("zip"):
                    msg_parts.append(f"ZIP: {r['zip']}")
                msg_parts.append(f"{r['copied']} file(s) copied")
                if r.get("generated"):
                    msg_parts.append(f"{r['generated']} support file(s) auto-generated")
                if r.get("errors"):
                    msg_parts.append(f"Errors: {len(r['errors'])}")
                    msg_parts.extend(f"  - {e}" for e in r["errors"][:5])
                msg_parts.append("")

            self.status.set(f"Generated: {name}")
            messagebox.showinfo("Success!", "\n".join(msg_parts))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate pack:\n{e}")

    def _prepare_pack_folder(self, name, out_dir, suffix=""):
        """Create a clean output folder; returns (folder_name, pack_root)."""
        folder_name = name.replace(" ", "_") + suffix
        pack_root = os.path.join(out_dir, folder_name)

        if os.path.exists(pack_root):
            if not messagebox.askyesno("Overwrite?",
                    f"'{folder_name}' already exists. Replace it?"):
                raise RuntimeError("Cancelled by user")
            shutil.rmtree(pack_root)
        os.makedirs(pack_root)
        return folder_name, pack_root

    def _zip_folder(self, pack_root, out_dir, folder_name):
        """ZIP a pack folder and return the zip path."""
        zip_path = os.path.join(out_dir, f"{folder_name}.zip")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_d, _, files in os.walk(pack_root):
                for file in files:
                    fp = os.path.join(root_d, file)
                    zf.write(fp, os.path.relpath(fp, pack_root))
        return zip_path

    # ─── JAVA EDITION ─────────────────────────────────────────────────

    def _generate_java_pack(self, name, out_dir):
        edition_suffix = "_Java" if "Both" in self.edition.get() else ""
        folder_name, pack_root = self._prepare_pack_folder(name, out_dir, edition_suffix)

        # Unpack format info (tuple: format_number, uses_new_system)
        # Check both hardcoded and dynamically fetched versions
        all_fmts = getattr(self, "_all_java_formats", JAVA_PACK_FORMATS)
        fmt_info = all_fmts.get(self.java_version.get(),
                                JAVA_PACK_FORMATS.get(self.java_version.get(),
                                                      (88, True)))
        fmt, uses_new = fmt_info

        # Build pack.mcmeta — two different schemas depending on version
        pack_section = {"description": self.description.get()}

        if uses_new:
            # New system (1.21.9+ / 26.x): min_format & max_format required
            pack_section["min_format"] = fmt
            pack_section["max_format"] = fmt
        else:
            # Legacy system (pre-1.21.9): pack_format required
            pack_section["pack_format"] = fmt
            # Add supported_formats range for 1.20.2+ (format 18+)
            if fmt >= 18:
                pack_section["supported_formats"] = {
                    "min_inclusive": 18, "max_inclusive": fmt
                }

        mcmeta = {"pack": pack_section}
        with open(os.path.join(pack_root, "pack.mcmeta"), "w") as f:
            json.dump(mcmeta, f, indent=4)

        # Pack icon
        if self.pack_icon_path and os.path.isfile(self.pack_icon_path):
            shutil.copy2(self.pack_icon_path, os.path.join(pack_root, "pack.png"))

        # Copy files
        copied, errors = self._copy_entries(pack_root, edition="java")

        # Auto-generate support files
        generated = self._java_auto_generate(pack_root)

        result = {"folder": pack_root, "copied": copied,
                  "generated": generated, "errors": errors}
        if self.zip_var.get():
            result["zip"] = self._zip_folder(pack_root, out_dir, folder_name)
        return result

    def _java_auto_generate(self, pack_root):
        """Auto-generate blockstates and item model JSONs for Java Edition."""
        count = 0
        models_dir = os.path.join(pack_root, "assets/minecraft/models")
        blockstates_dir = os.path.join(pack_root, "assets/minecraft/blockstates")

        # Blockstates for block models
        block_models_dir = os.path.join(models_dir, "block")
        if os.path.isdir(block_models_dir):
            os.makedirs(blockstates_dir, exist_ok=True)
            for fname in os.listdir(block_models_dir):
                if not fname.endswith(".json"):
                    continue
                bs_path = os.path.join(blockstates_dir, fname)
                if not os.path.exists(bs_path):
                    model_name = os.path.splitext(fname)[0]
                    bs_data = {"variants": {"": {"model": f"minecraft:block/{model_name}"}}}
                    with open(bs_path, "w") as f:
                        json.dump(bs_data, f, indent=2)
                    count += 1

        # Item model JSONs for item textures
        item_textures_dir = os.path.join(pack_root, "assets/minecraft/textures/item")
        item_models_dir = os.path.join(models_dir, "item")
        if os.path.isdir(item_textures_dir):
            os.makedirs(item_models_dir, exist_ok=True)
            for fname in os.listdir(item_textures_dir):
                if not fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                model_name = os.path.splitext(fname)[0]
                model_path = os.path.join(item_models_dir, f"{model_name}.json")
                if not os.path.exists(model_path):
                    parent = "minecraft:item/generated"
                    handheld = ["sword", "pickaxe", "axe", "shovel", "hoe",
                                "trident", "rod", "stick", "blaze_rod"]
                    if any(h in model_name for h in handheld):
                        parent = "minecraft:item/handheld"
                    model_data = {
                        "parent": parent,
                        "textures": {"layer0": f"minecraft:item/{model_name}"}
                    }
                    with open(model_path, "w") as f:
                        json.dump(model_data, f, indent=2)
                    count += 1

        # Auto-detect emissive textures (_e suffix) and generate
        # OptiFine emissive.properties if any are found
        count += self._generate_emissive_properties(pack_root)

        return count

    def _generate_emissive_properties(self, pack_root):
        """Detect _e suffix textures and auto-generate emissive.properties."""
        textures_root = os.path.join(pack_root, "assets/minecraft/textures")
        if not os.path.isdir(textures_root):
            return 0

        # Walk all texture files looking for the _e emissive pattern
        has_emissive = False
        for root_d, _, files in os.walk(textures_root):
            for fname in files:
                if not fname.lower().endswith('.png'):
                    continue
                name = os.path.splitext(fname)[0]
                # Check for _e suffix (OptiFine emissive convention)
                if name.endswith("_e"):
                    has_emissive = True
                    break
            if has_emissive:
                break

        if not has_emissive:
            return 0

        # Generate emissive.properties if it doesn't already exist
        optifine_dir = os.path.join(pack_root, "assets/minecraft/optifine")
        props_path = os.path.join(optifine_dir, "emissive.properties")
        if os.path.exists(props_path):
            return 0

        os.makedirs(optifine_dir, exist_ok=True)
        with open(props_path, "w") as f:
            f.write("suffix.emissive=_e\n")
        return 1

    # ─── BEDROCK EDITION ──────────────────────────────────────────────

    @staticmethod
    def _java_path_to_bedrock(java_dest):
        """Convert a Java Edition destination path to Bedrock Edition equivalent.
        Returns None for paths that have no Bedrock equivalent (e.g. OptiFine)."""

        # Skip Java-only paths
        if "optifine" in java_dest or "blockstates" in java_dest:
            return None
        if java_dest.endswith((".jem", ".properties")):
            return None

        p = java_dest

        # assets/minecraft/textures/block/X.png -> textures/blocks/X.png
        p = p.replace("assets/minecraft/textures/block/", "textures/blocks/")
        # assets/minecraft/textures/item/X.png  -> textures/items/X.png
        p = p.replace("assets/minecraft/textures/item/", "textures/items/")
        # assets/minecraft/textures/entity/X.png -> textures/entity/X.png
        p = p.replace("assets/minecraft/textures/entity/", "textures/entity/")
        # assets/minecraft/textures/models/armor/X.png -> textures/models/armor/X.png
        p = p.replace("assets/minecraft/textures/models/armor/", "textures/models/armor/")
        # assets/minecraft/textures/gui/X.png -> textures/gui/X.png
        p = p.replace("assets/minecraft/textures/gui/", "textures/gui/")
        # assets/minecraft/textures/environment/X.png -> textures/environment/X.png
        p = p.replace("assets/minecraft/textures/environment/", "textures/environment/")
        # assets/minecraft/textures/painting/X.png -> textures/painting/X.png
        p = p.replace("assets/minecraft/textures/painting/", "textures/painting/")
        # Generic fallback
        p = p.replace("assets/minecraft/textures/", "textures/")
        # Models (Bedrock uses different format, but we can try)
        p = p.replace("assets/minecraft/models/", "models/")
        # Final fallback: strip assets/minecraft/ prefix
        p = p.replace("assets/minecraft/", "")

        return p

    def _generate_bedrock_pack(self, name, out_dir):
        edition_suffix = "_Bedrock" if "Both" in self.edition.get() else ""
        folder_name, pack_root = self._prepare_pack_folder(name, out_dir, edition_suffix)

        # manifest.json
        min_ver = BEDROCK_VERSIONS.get(self.bedrock_version.get(), [1, 21, 0])
        pack_uuid = str(uuid.uuid4())
        module_uuid = str(uuid.uuid4())

        manifest = {
            "format_version": 2,
            "header": {
                "name": name,
                "description": self.description.get(),
                "uuid": pack_uuid,
                "version": [1, 0, 0],
                "min_engine_version": min_ver
            },
            "modules": [
                {
                    "type": "resources",
                    "uuid": module_uuid,
                    "version": [1, 0, 0],
                    "description": self.description.get()
                }
            ]
        }
        with open(os.path.join(pack_root, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=4)

        # Pack icon (Bedrock uses pack_icon.png)
        if self.pack_icon_path and os.path.isfile(self.pack_icon_path):
            shutil.copy2(self.pack_icon_path, os.path.join(pack_root, "pack_icon.png"))

        # Copy files with path conversion
        copied, errors = self._copy_entries(pack_root, edition="bedrock")

        # Auto-generate Bedrock support files
        generated = self._bedrock_auto_generate(pack_root)

        result = {"folder": pack_root, "copied": copied,
                  "generated": generated, "errors": errors}
        if self.zip_var.get():
            # Bedrock uses .mcpack (which is just a renamed zip)
            zip_path = os.path.join(out_dir, f"{folder_name}.mcpack")
            if os.path.exists(zip_path):
                os.remove(zip_path)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root_d, _, files in os.walk(pack_root):
                    for file in files:
                        fp = os.path.join(root_d, file)
                        zf.write(fp, os.path.relpath(fp, pack_root))
            result["zip"] = zip_path
        return result

    def _bedrock_auto_generate(self, pack_root):
        """Auto-generate Bedrock-specific support files:
        - terrain_texture.json for block textures
        - item_texture.json for item textures
        - textures_list.json listing all texture files
        """
        count = 0
        textures_dir = os.path.join(pack_root, "textures")

        # terrain_texture.json — maps block texture short names
        blocks_dir = os.path.join(textures_dir, "blocks")
        if os.path.isdir(blocks_dir):
            texture_data = {}
            for fname in os.listdir(blocks_dir):
                if not fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                short_name = os.path.splitext(fname)[0]
                texture_data[short_name] = {
                    "textures": f"textures/blocks/{short_name}"
                }
            if texture_data:
                terrain = {
                    "resource_pack_name": self.pack_name.get(),
                    "texture_name": "atlas.terrain",
                    "padding": 8,
                    "num_mip_levels": 4,
                    "texture_data": texture_data
                }
                with open(os.path.join(textures_dir, "terrain_texture.json"), "w") as f:
                    json.dump(terrain, f, indent=2)
                count += 1

        # item_texture.json — maps item texture short names
        items_dir = os.path.join(textures_dir, "items")
        if os.path.isdir(items_dir):
            texture_data = {}
            for fname in os.listdir(items_dir):
                if not fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                short_name = os.path.splitext(fname)[0]
                texture_data[short_name] = {
                    "textures": f"textures/items/{short_name}"
                }
            if texture_data:
                items_json = {
                    "resource_pack_name": self.pack_name.get(),
                    "texture_name": "atlas.items",
                    "texture_data": texture_data
                }
                with open(os.path.join(textures_dir, "item_texture.json"), "w") as f:
                    json.dump(items_json, f, indent=2)
                count += 1

        # textures_list.json — enumerates all texture paths
        if os.path.isdir(textures_dir):
            tex_list = []
            for root_d, _, files in os.walk(textures_dir):
                for fname in files:
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.tga')):
                        rel = os.path.relpath(
                            os.path.join(root_d, fname), pack_root
                        ).replace("\\", "/")
                        # Strip extension for textures_list
                        tex_list.append(os.path.splitext(rel)[0])
            if tex_list:
                with open(os.path.join(textures_dir, "textures_list.json"), "w") as f:
                    json.dump(sorted(tex_list), f, indent=2)
                count += 1

        return count

    # ─── SHARED COPY LOGIC ────────────────────────────────────────────

    def _copy_entries(self, pack_root, edition="java"):
        """Copy all entries into the pack folder, converting paths for Bedrock."""
        copied = 0
        errors = []
        for entry in self.entries:
            src = entry["source_file"]
            java_dest = entry["dest_path"]

            if edition == "bedrock":
                dest_rel = self._java_path_to_bedrock(java_dest)
                if dest_rel is None:
                    continue  # Skip Java-only files
            else:
                dest_rel = java_dest

            dest = os.path.join(pack_root, dest_rel)
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                copied += 1
            except Exception as e:
                errors.append(f"{entry['display_name']}: {e}")
        return copied, errors


def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    app = ResourcePackGenerator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
