#!/usr/bin/env python3
"""
Demo Content Generator Script
Generates 200+ demo examples using GoEnhance API for before/after style transformation showcase.

Usage:
    cd backend
    uv run python scripts/generate_demos.py --count 200 --dry-run  # Preview only
    uv run python scripts/generate_demos.py --count 200            # Actually generate
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.goenhance import GoEnhanceClient
from app.core.config import get_settings

settings = get_settings()


# =============================================================================
# DEMO TOPICS AND PROMPTS (200+ items organized by category)
# =============================================================================

DEMO_TOPICS = {
    "animals": [
        {"prompt": "A cute cat sitting on a windowsill watching birds", "keywords": ["cat", "window", "birds", "pet"]},
        {"prompt": "A golden retriever playing fetch in the park", "keywords": ["dog", "golden retriever", "park", "play"]},
        {"prompt": "A majestic lion walking through the savanna", "keywords": ["lion", "savanna", "wildlife", "majestic"]},
        {"prompt": "Colorful tropical fish swimming in coral reef", "keywords": ["fish", "coral", "tropical", "underwater"]},
        {"prompt": "A wise owl perched on an ancient tree branch", "keywords": ["owl", "tree", "wise", "night"]},
        {"prompt": "Playful dolphins jumping over ocean waves", "keywords": ["dolphin", "ocean", "waves", "play"]},
        {"prompt": "A red panda sleeping on a bamboo branch", "keywords": ["panda", "bamboo", "cute", "sleeping"]},
        {"prompt": "Elephants crossing a river at sunset", "keywords": ["elephant", "river", "sunset", "africa"]},
        {"prompt": "A butterfly landing on a colorful flower", "keywords": ["butterfly", "flower", "nature", "spring"]},
        {"prompt": "Arctic fox in a snowy winter landscape", "keywords": ["fox", "arctic", "snow", "winter"]},
        {"prompt": "A parrot with vibrant colorful feathers", "keywords": ["parrot", "colorful", "bird", "tropical"]},
        {"prompt": "Horse galloping through a meadow", "keywords": ["horse", "gallop", "meadow", "freedom"]},
        {"prompt": "Penguin family on Antarctic ice", "keywords": ["penguin", "ice", "antarctic", "family"]},
        {"prompt": "A cheetah running at full speed", "keywords": ["cheetah", "running", "speed", "wildlife"]},
        {"prompt": "Koala bear hugging a eucalyptus tree", "keywords": ["koala", "eucalyptus", "australia", "cute"]},
    ],
    "nature": [
        {"prompt": "Breathtaking sunset over the ocean horizon", "keywords": ["sunset", "ocean", "horizon", "sky"]},
        {"prompt": "Majestic waterfall in a tropical rainforest", "keywords": ["waterfall", "rainforest", "tropical", "water"]},
        {"prompt": "Cherry blossoms in full bloom in spring", "keywords": ["cherry blossom", "spring", "pink", "japan"]},
        {"prompt": "Northern lights dancing over snowy mountains", "keywords": ["aurora", "northern lights", "mountains", "night"]},
        {"prompt": "Peaceful zen garden with raked sand patterns", "keywords": ["zen", "garden", "peaceful", "meditation"]},
        {"prompt": "Dramatic lightning storm over a desert landscape", "keywords": ["lightning", "storm", "desert", "dramatic"]},
        {"prompt": "Crystal clear lake reflecting mountain peaks", "keywords": ["lake", "mountains", "reflection", "clear"]},
        {"prompt": "Autumn forest with colorful falling leaves", "keywords": ["autumn", "forest", "leaves", "fall"]},
        {"prompt": "Misty morning in an ancient forest", "keywords": ["mist", "forest", "morning", "mysterious"]},
        {"prompt": "Volcanic eruption with flowing lava", "keywords": ["volcano", "lava", "eruption", "fire"]},
        {"prompt": "Vast field of sunflowers under blue sky", "keywords": ["sunflower", "field", "summer", "yellow"]},
        {"prompt": "Icy glacier calving into the sea", "keywords": ["glacier", "ice", "arctic", "ocean"]},
        {"prompt": "Rainbow appearing after a rain shower", "keywords": ["rainbow", "rain", "colorful", "sky"]},
        {"prompt": "Desert sand dunes at golden hour", "keywords": ["desert", "dunes", "sand", "golden"]},
        {"prompt": "Starry night sky over a mountain peak", "keywords": ["stars", "night", "mountain", "galaxy"]},
    ],
    "urban": [
        {"prompt": "Neon-lit Tokyo street at night with rain", "keywords": ["tokyo", "neon", "night", "rain", "city"]},
        {"prompt": "New York City skyline at sunset", "keywords": ["new york", "skyline", "sunset", "city"]},
        {"prompt": "Cozy European cafe on a cobblestone street", "keywords": ["cafe", "europe", "street", "cozy"]},
        {"prompt": "Modern glass skyscraper reflecting clouds", "keywords": ["skyscraper", "modern", "glass", "architecture"]},
        {"prompt": "Vintage car driving through city streets", "keywords": ["car", "vintage", "city", "retro"]},
        {"prompt": "Busy night market with colorful lanterns", "keywords": ["market", "night", "lanterns", "asia"]},
        {"prompt": "Street artist creating graffiti mural", "keywords": ["graffiti", "street art", "urban", "colorful"]},
        {"prompt": "Iconic London double-decker bus", "keywords": ["london", "bus", "red", "iconic"]},
        {"prompt": "Floating market in Thailand", "keywords": ["market", "boat", "thailand", "floating"]},
        {"prompt": "Paris Eiffel Tower at dusk", "keywords": ["paris", "eiffel tower", "dusk", "france"]},
        {"prompt": "Underground subway station with motion blur", "keywords": ["subway", "train", "motion", "underground"]},
        {"prompt": "Rooftop bar overlooking city lights", "keywords": ["rooftop", "bar", "city", "night"]},
        {"prompt": "Traditional Japanese temple in modern city", "keywords": ["temple", "japan", "traditional", "contrast"]},
        {"prompt": "Cyclist crossing a bridge at sunrise", "keywords": ["bicycle", "bridge", "sunrise", "urban"]},
        {"prompt": "Historic castle illuminated at night", "keywords": ["castle", "night", "historic", "lights"]},
    ],
    "people": [
        {"prompt": "Dancer performing ballet in elegant pose", "keywords": ["dancer", "ballet", "elegant", "performance"]},
        {"prompt": "Samurai warrior in traditional armor", "keywords": ["samurai", "warrior", "japan", "armor"]},
        {"prompt": "Chef preparing gourmet dish in kitchen", "keywords": ["chef", "cooking", "kitchen", "food"]},
        {"prompt": "Astronaut floating in space with Earth view", "keywords": ["astronaut", "space", "earth", "floating"]},
        {"prompt": "Street musician playing guitar", "keywords": ["musician", "guitar", "street", "music"]},
        {"prompt": "Martial artist performing high kick", "keywords": ["martial arts", "kick", "action", "fighter"]},
        {"prompt": "Fashion model on runway with dramatic lighting", "keywords": ["fashion", "model", "runway", "style"]},
        {"prompt": "Scientist working in futuristic laboratory", "keywords": ["scientist", "lab", "future", "research"]},
        {"prompt": "Photographer capturing sunset moment", "keywords": ["photographer", "camera", "sunset", "creative"]},
        {"prompt": "Yoga practitioner in meditation pose", "keywords": ["yoga", "meditation", "peaceful", "wellness"]},
        {"prompt": "Surfer riding a massive wave", "keywords": ["surfer", "wave", "ocean", "extreme"]},
        {"prompt": "Artist painting on large canvas", "keywords": ["artist", "painting", "creative", "studio"]},
        {"prompt": "Couple dancing under starlight", "keywords": ["couple", "dance", "romantic", "night"]},
        {"prompt": "Firefighter in action saving lives", "keywords": ["firefighter", "hero", "action", "brave"]},
        {"prompt": "Child blowing bubbles in garden", "keywords": ["child", "bubbles", "garden", "playful"]},
    ],
    "fantasy": [
        {"prompt": "Majestic dragon flying over castle", "keywords": ["dragon", "castle", "fantasy", "flying"]},
        {"prompt": "Mystical unicorn in enchanted forest", "keywords": ["unicorn", "forest", "magical", "enchanted"]},
        {"prompt": "Wizard casting spell with glowing magic", "keywords": ["wizard", "magic", "spell", "fantasy"]},
        {"prompt": "Fairy with glowing wings in moonlight", "keywords": ["fairy", "wings", "moonlight", "magical"]},
        {"prompt": "Ancient temple ruins with mystical energy", "keywords": ["temple", "ruins", "mystical", "ancient"]},
        {"prompt": "Phoenix rising from flames", "keywords": ["phoenix", "fire", "rebirth", "mythical"]},
        {"prompt": "Mermaid swimming in crystal waters", "keywords": ["mermaid", "underwater", "crystal", "fantasy"]},
        {"prompt": "Knight in shining armor on horseback", "keywords": ["knight", "armor", "horse", "medieval"]},
        {"prompt": "Floating islands in a magical sky", "keywords": ["islands", "floating", "sky", "magical"]},
        {"prompt": "Giant tree with glowing runes", "keywords": ["tree", "runes", "glowing", "magical"]},
        {"prompt": "Portal to another dimension opening", "keywords": ["portal", "dimension", "magical", "gateway"]},
        {"prompt": "Elf archer in mystical woodland", "keywords": ["elf", "archer", "woodland", "fantasy"]},
        {"prompt": "Crystal cave with magical gems", "keywords": ["cave", "crystal", "gems", "magical"]},
        {"prompt": "Steampunk airship in cloudy sky", "keywords": ["steampunk", "airship", "sky", "mechanical"]},
        {"prompt": "Enchanted library with floating books", "keywords": ["library", "books", "floating", "magical"]},
    ],
    "sci-fi": [
        {"prompt": "Futuristic city with flying vehicles", "keywords": ["future", "city", "flying cars", "sci-fi"]},
        {"prompt": "Robot with human-like expressions", "keywords": ["robot", "android", "ai", "futuristic"]},
        {"prompt": "Spaceship landing on alien planet", "keywords": ["spaceship", "alien", "planet", "landing"]},
        {"prompt": "Cyberpunk hacker with neon implants", "keywords": ["cyberpunk", "hacker", "neon", "cyber"]},
        {"prompt": "Space station orbiting distant planet", "keywords": ["space station", "orbit", "planet", "space"]},
        {"prompt": "Alien creature with bioluminescent features", "keywords": ["alien", "bioluminescent", "creature", "exotic"]},
        {"prompt": "Time travel portal with swirling energy", "keywords": ["time travel", "portal", "energy", "sci-fi"]},
        {"prompt": "Mech warrior in battle stance", "keywords": ["mech", "robot", "battle", "warrior"]},
        {"prompt": "Holographic display of galaxy map", "keywords": ["hologram", "galaxy", "map", "technology"]},
        {"prompt": "Laser battle in space between ships", "keywords": ["laser", "space", "battle", "ships"]},
        {"prompt": "Terraformed Mars colony settlement", "keywords": ["mars", "colony", "terraformed", "future"]},
        {"prompt": "AI consciousness visualization", "keywords": ["ai", "consciousness", "digital", "abstract"]},
        {"prompt": "Cryogenic pod with sleeping passenger", "keywords": ["cryogenic", "pod", "sleep", "sci-fi"]},
        {"prompt": "Quantum computer with glowing circuits", "keywords": ["quantum", "computer", "circuits", "technology"]},
        {"prompt": "Alien sunset with multiple moons", "keywords": ["alien", "sunset", "moons", "planet"]},
    ],
    "food": [
        {"prompt": "Gourmet sushi platter with fresh fish", "keywords": ["sushi", "japanese", "fresh", "gourmet"]},
        {"prompt": "Steaming bowl of ramen with toppings", "keywords": ["ramen", "noodles", "japanese", "hot"]},
        {"prompt": "Artisan pizza fresh from wood oven", "keywords": ["pizza", "italian", "oven", "cheese"]},
        {"prompt": "Colorful macarons in pastel shades", "keywords": ["macarons", "french", "colorful", "dessert"]},
        {"prompt": "Juicy burger with all the toppings", "keywords": ["burger", "american", "juicy", "food"]},
        {"prompt": "Fresh fruit smoothie bowl", "keywords": ["smoothie", "fruit", "healthy", "bowl"]},
        {"prompt": "Decadent chocolate cake with ganache", "keywords": ["chocolate", "cake", "dessert", "rich"]},
        {"prompt": "Traditional dim sum in bamboo steamer", "keywords": ["dim sum", "chinese", "steamer", "traditional"]},
        {"prompt": "Colorful Indian curry spread", "keywords": ["curry", "indian", "spicy", "colorful"]},
        {"prompt": "Fresh croissant with butter and jam", "keywords": ["croissant", "french", "pastry", "breakfast"]},
        {"prompt": "Grilled steak with vegetables", "keywords": ["steak", "grill", "meat", "dinner"]},
        {"prompt": "Ice cream sundae with toppings", "keywords": ["ice cream", "sundae", "dessert", "sweet"]},
        {"prompt": "Coffee latte art in ceramic cup", "keywords": ["coffee", "latte art", "cafe", "drink"]},
        {"prompt": "Mediterranean mezze platter", "keywords": ["mediterranean", "mezze", "healthy", "varied"]},
        {"prompt": "Fresh seafood platter on ice", "keywords": ["seafood", "fresh", "ocean", "platter"]},
    ],
    "abstract": [
        {"prompt": "Flowing liquid metal in slow motion", "keywords": ["liquid", "metal", "abstract", "flowing"]},
        {"prompt": "Geometric patterns with neon colors", "keywords": ["geometric", "neon", "patterns", "abstract"]},
        {"prompt": "Smoke swirls in colorful light", "keywords": ["smoke", "colorful", "light", "abstract"]},
        {"prompt": "Fractal patterns in vivid colors", "keywords": ["fractal", "patterns", "vivid", "mathematical"]},
        {"prompt": "Paint splatter explosion of colors", "keywords": ["paint", "splash", "explosion", "colorful"]},
        {"prompt": "Kaleidoscope effect with gems", "keywords": ["kaleidoscope", "gems", "symmetry", "colorful"]},
        {"prompt": "Aurora waves in abstract form", "keywords": ["aurora", "waves", "abstract", "ethereal"]},
        {"prompt": "Digital particles forming patterns", "keywords": ["digital", "particles", "patterns", "tech"]},
        {"prompt": "Marble texture with gold veins", "keywords": ["marble", "gold", "texture", "luxury"]},
        {"prompt": "Ink drops diffusing in water", "keywords": ["ink", "water", "diffusion", "art"]},
        {"prompt": "Neon light trails in motion", "keywords": ["neon", "light trails", "motion", "dynamic"]},
        {"prompt": "Crystal formations with light refraction", "keywords": ["crystal", "light", "refraction", "natural"]},
        {"prompt": "Sound wave visualization", "keywords": ["sound", "wave", "music", "visualization"]},
        {"prompt": "Bubble cluster with rainbow reflections", "keywords": ["bubbles", "rainbow", "reflections", "light"]},
        {"prompt": "Fire and ice collision abstract", "keywords": ["fire", "ice", "collision", "contrast"]},
    ],
    "sports": [
        {"prompt": "Soccer player scoring dramatic goal", "keywords": ["soccer", "goal", "sports", "action"]},
        {"prompt": "Basketball slam dunk in mid-air", "keywords": ["basketball", "dunk", "action", "sports"]},
        {"prompt": "Swimmer diving into crystal pool", "keywords": ["swimming", "dive", "pool", "water"]},
        {"prompt": "Tennis serve at maximum power", "keywords": ["tennis", "serve", "power", "sports"]},
        {"prompt": "Skateboarder performing aerial trick", "keywords": ["skateboard", "trick", "aerial", "extreme"]},
        {"prompt": "Rock climber on vertical cliff", "keywords": ["climbing", "rock", "cliff", "extreme"]},
        {"prompt": "Snowboarder in powder snow jump", "keywords": ["snowboard", "snow", "jump", "winter"]},
        {"prompt": "Racing car on track with motion blur", "keywords": ["racing", "car", "speed", "motorsport"]},
        {"prompt": "Golfer perfect swing on green", "keywords": ["golf", "swing", "green", "sport"]},
        {"prompt": "Yoga pose on mountaintop at sunrise", "keywords": ["yoga", "mountain", "sunrise", "wellness"]},
        {"prompt": "BMX rider doing backflip", "keywords": ["bmx", "flip", "extreme", "cycling"]},
        {"prompt": "Boxing match punch in action", "keywords": ["boxing", "punch", "fight", "sports"]},
        {"prompt": "Skier racing down mountain slope", "keywords": ["skiing", "mountain", "snow", "speed"]},
        {"prompt": "Martial arts flying kick", "keywords": ["martial arts", "kick", "action", "combat"]},
        {"prompt": "Volleyball spike at the net", "keywords": ["volleyball", "spike", "beach", "sports"]},
    ],
    "music": [
        {"prompt": "Rock guitarist performing solo on stage", "keywords": ["guitar", "rock", "concert", "performance"]},
        {"prompt": "DJ mixing at neon-lit club", "keywords": ["dj", "club", "neon", "electronic"]},
        {"prompt": "Classical pianist at grand piano", "keywords": ["piano", "classical", "elegant", "music"]},
        {"prompt": "Drummer with explosive energy", "keywords": ["drums", "energy", "rock", "performance"]},
        {"prompt": "Orchestra performing in concert hall", "keywords": ["orchestra", "classical", "concert", "elegant"]},
        {"prompt": "Street violinist at sunset", "keywords": ["violin", "street", "sunset", "romantic"]},
        {"prompt": "Hip hop dancer with graffiti backdrop", "keywords": ["hip hop", "dance", "graffiti", "urban"]},
        {"prompt": "Jazz saxophonist in smoky club", "keywords": ["jazz", "saxophone", "club", "classic"]},
        {"prompt": "K-pop group dance performance", "keywords": ["kpop", "dance", "group", "colorful"]},
        {"prompt": "Acoustic guitar by campfire", "keywords": ["acoustic", "campfire", "cozy", "night"]},
        {"prompt": "Electronic music visualizer", "keywords": ["electronic", "visualizer", "abstract", "music"]},
        {"prompt": "Opera singer in dramatic lighting", "keywords": ["opera", "singer", "dramatic", "classical"]},
        {"prompt": "Festival crowd with confetti", "keywords": ["festival", "crowd", "confetti", "celebration"]},
        {"prompt": "Record player with vinyl spinning", "keywords": ["vinyl", "retro", "music", "analog"]},
        {"prompt": "Music studio with equipment", "keywords": ["studio", "equipment", "professional", "production"]},
    ],
    "seasonal": [
        {"prompt": "Christmas tree with twinkling lights", "keywords": ["christmas", "tree", "lights", "holiday"]},
        {"prompt": "Halloween jack-o-lantern at night", "keywords": ["halloween", "pumpkin", "spooky", "night"]},
        {"prompt": "Spring cherry blossoms in Japan", "keywords": ["spring", "cherry blossom", "japan", "pink"]},
        {"prompt": "Summer beach with palm trees", "keywords": ["summer", "beach", "palm trees", "tropical"]},
        {"prompt": "Autumn leaves falling in park", "keywords": ["autumn", "leaves", "fall", "colorful"]},
        {"prompt": "Winter wonderland snowy scene", "keywords": ["winter", "snow", "wonderland", "cold"]},
        {"prompt": "New Year fireworks over city", "keywords": ["new year", "fireworks", "celebration", "night"]},
        {"prompt": "Valentine heart-shaped decorations", "keywords": ["valentine", "hearts", "romantic", "love"]},
        {"prompt": "Easter eggs in spring garden", "keywords": ["easter", "eggs", "spring", "colorful"]},
        {"prompt": "Thanksgiving harvest table spread", "keywords": ["thanksgiving", "harvest", "food", "autumn"]},
        {"prompt": "Chinese New Year dragon dance", "keywords": ["chinese new year", "dragon", "celebration", "red"]},
        {"prompt": "Diwali festival of lights celebration", "keywords": ["diwali", "lights", "festival", "colorful"]},
        {"prompt": "Midsummer bonfire at beach", "keywords": ["midsummer", "bonfire", "beach", "night"]},
        {"prompt": "Carnival parade with colorful costumes", "keywords": ["carnival", "parade", "colorful", "festive"]},
        {"prompt": "Lantern festival floating lights", "keywords": ["lantern", "festival", "floating", "night"]},
    ],
    "architecture": [
        {"prompt": "Gothic cathedral with stained glass", "keywords": ["cathedral", "gothic", "stained glass", "historic"]},
        {"prompt": "Modern minimalist house design", "keywords": ["modern", "minimalist", "house", "architecture"]},
        {"prompt": "Ancient Roman colosseum", "keywords": ["colosseum", "roman", "ancient", "historic"]},
        {"prompt": "Japanese traditional pagoda", "keywords": ["pagoda", "japanese", "traditional", "temple"]},
        {"prompt": "Futuristic Dubai skyscrapers", "keywords": ["dubai", "skyscraper", "futuristic", "modern"]},
        {"prompt": "Rustic wooden cabin in mountains", "keywords": ["cabin", "wooden", "mountains", "rustic"]},
        {"prompt": "Art deco building facade", "keywords": ["art deco", "building", "vintage", "elegant"]},
        {"prompt": "Ancient Egyptian pyramids", "keywords": ["pyramids", "egypt", "ancient", "desert"]},
        {"prompt": "Zen Buddhist temple garden", "keywords": ["zen", "temple", "garden", "peaceful"]},
        {"prompt": "Industrial loft interior design", "keywords": ["loft", "industrial", "interior", "modern"]},
        {"prompt": "Treehouse in giant redwood", "keywords": ["treehouse", "redwood", "nature", "unique"]},
        {"prompt": "Greek island white buildings", "keywords": ["greek", "white", "island", "mediterranean"]},
        {"prompt": "Moroccan palace with tiles", "keywords": ["moroccan", "palace", "tiles", "exotic"]},
        {"prompt": "Suspension bridge at sunset", "keywords": ["bridge", "suspension", "sunset", "engineering"]},
        {"prompt": "Underground cave dwelling", "keywords": ["cave", "underground", "unique", "dwelling"]},
    ],
    "vehicles": [
        {"prompt": "Classic vintage sports car", "keywords": ["vintage", "sports car", "classic", "retro"]},
        {"prompt": "Futuristic concept electric car", "keywords": ["electric", "concept", "future", "car"]},
        {"prompt": "Motorcycle on coastal highway", "keywords": ["motorcycle", "highway", "coastal", "freedom"]},
        {"prompt": "Steam locomotive through mountains", "keywords": ["train", "steam", "mountains", "vintage"]},
        {"prompt": "Yacht sailing on crystal waters", "keywords": ["yacht", "sailing", "ocean", "luxury"]},
        {"prompt": "Helicopter over city skyline", "keywords": ["helicopter", "city", "aerial", "flight"]},
        {"prompt": "Vintage airplane at sunset", "keywords": ["airplane", "vintage", "sunset", "aviation"]},
        {"prompt": "Submarine exploring deep ocean", "keywords": ["submarine", "ocean", "deep", "exploration"]},
        {"prompt": "Hot air balloon over landscape", "keywords": ["balloon", "hot air", "landscape", "peaceful"]},
        {"prompt": "Racing speedboat on lake", "keywords": ["speedboat", "racing", "lake", "water"]},
        {"prompt": "Luxury limousine at night", "keywords": ["limousine", "luxury", "night", "elegant"]},
        {"prompt": "Dirt bike jumping dunes", "keywords": ["dirt bike", "jump", "dunes", "extreme"]},
        {"prompt": "Classic train station platform", "keywords": ["train station", "classic", "platform", "travel"]},
        {"prompt": "Space shuttle launch", "keywords": ["space shuttle", "launch", "rocket", "space"]},
        {"prompt": "Rickshaw in Asian street", "keywords": ["rickshaw", "asian", "street", "traditional"]},
    ],
}

# Available GoEnhance styles with descriptions (from actual API)
GOENHANCE_STYLES = [
    {"id": 2, "name": "Anime Style 2", "slug": "anime_v1", "description": "Classic anime style v1"},
    {"id": 5, "name": "Cute Anime Style", "slug": "cute_anime", "description": "Kawaii cute anime style"},
    {"id": 1016, "name": "Anime Style 3", "slug": "anime_v4", "description": "Anime style v4"},
    {"id": 1033, "name": "GPT Anime Style", "slug": "gpt_anime", "description": "GPT-enhanced anime style"},
    {"id": 2000, "name": "Anime Style", "slug": "anime_v5", "description": "Latest anime style v5"},
    {"id": 2004, "name": "Pixar Style", "slug": "pixar", "description": "3D Pixar animation style"},
    {"id": 2005, "name": "Clay Style", "slug": "clay", "description": "Claymation stop-motion style"},
    {"id": 2006, "name": "Oil Painting", "slug": "oil_painting", "description": "Classic oil painting artistic style"},
    {"id": 2007, "name": "Watercolor", "slug": "watercolor", "description": "Soft watercolor painting style"},
    {"id": 2008, "name": "Cyberpunk", "slug": "cyberpunk", "description": "Neon cyberpunk futuristic style"},
    {"id": 2009, "name": "Realistic", "slug": "realistic", "description": "Enhanced realistic rendering"},
    {"id": 2010, "name": "Cinematic", "slug": "cinematic", "description": "Hollywood cinematic look"},
]


def get_all_topics() -> List[Dict[str, Any]]:
    """Flatten all topics with category info"""
    all_topics = []
    for category, topics in DEMO_TOPICS.items():
        for topic in topics:
            all_topics.append({
                **topic,
                "category": category
            })
    return all_topics


def generate_demo_combinations(count: int = 200) -> List[Dict[str, Any]]:
    """
    Generate demo combinations pairing topics with styles

    Each demo will show:
    - Original prompt/topic
    - Style transformation applied
    - Before (original) and After (styled) comparison
    """
    all_topics = get_all_topics()
    combinations = []

    # Calculate how many styles per topic to reach target count
    styles_per_topic = max(1, count // len(all_topics))

    for topic in all_topics:
        # Select random styles for this topic
        selected_styles = random.sample(GOENHANCE_STYLES, min(styles_per_topic, len(GOENHANCE_STYLES)))

        for style in selected_styles:
            if len(combinations) >= count:
                break

            combinations.append({
                "title": f"{topic['prompt'][:50]} - {style['name']}",
                "prompt": topic["prompt"],
                "keywords": topic["keywords"] + [style["slug"]],
                "category": topic["category"],
                "style_id": style["id"],
                "style_name": style["name"],
                "style_slug": style["slug"],
                "style_description": style["description"],
            })

        if len(combinations) >= count:
            break

    # If we need more, add more random combinations
    while len(combinations) < count:
        topic = random.choice(all_topics)
        style = random.choice(GOENHANCE_STYLES)
        combinations.append({
            "title": f"{topic['prompt'][:50]} - {style['name']}",
            "prompt": topic["prompt"],
            "keywords": topic["keywords"] + [style["slug"]],
            "category": topic["category"],
            "style_id": style["id"],
            "style_name": style["name"],
            "style_slug": style["slug"],
            "style_description": style["description"],
        })

    return combinations[:count]


async def check_api_credits(client: GoEnhanceClient) -> Dict[str, Any]:
    """Check available API credits"""
    credits = await client.get_credits()
    print(f"\n💰 API Credits: {json.dumps(credits, indent=2)}")
    return credits


async def generate_single_demo(
    client: GoEnhanceClient,
    demo: Dict[str, Any],
    source_video_url: str,
    index: int,
    total: int,
    dry_run: bool = False
) -> Optional[Dict[str, Any]]:
    """Generate a single demo transformation"""

    print(f"\n[{index + 1}/{total}] Generating: {demo['title']}")
    print(f"   Style: {demo['style_name']} (ID: {demo['style_id']})")
    print(f"   Category: {demo['category']}")

    if dry_run:
        print("   ⏭️  Dry run - skipping API call")
        return {
            **demo,
            "status": "dry_run",
            "video_url_before": source_video_url,
            "video_url_after": None,
            "thumbnail_url": None,
        }

    # Generate transformation
    success, task_id_or_error, _ = await client.generate_v2v(
        video_url=source_video_url,
        model_id=demo["style_id"],
        duration=5,
        prompt=demo["prompt"][:200]
    )

    if not success:
        print(f"   ❌ Failed to start: {task_id_or_error}")
        return {
            **demo,
            "status": "failed",
            "error": task_id_or_error,
            "video_url_before": source_video_url,
            "video_url_after": None,
        }

    print(f"   ⏳ Task started: {task_id_or_error}")

    # Wait for completion
    result = await client.wait_for_completion(task_id_or_error, timeout=300, poll_interval=10)

    if result.get("status") == "completed":
        print(f"   ✅ Completed: {result.get('result_url', '')[:50]}...")
        return {
            **demo,
            "status": "completed",
            "task_id": task_id_or_error,
            "video_url_before": source_video_url,
            "video_url_after": result.get("result_url"),
            "thumbnail_url": result.get("thumbnail_url"),
        }
    else:
        print(f"   ❌ Failed: {result.get('status')} - {result.get('error', '')}")
        return {
            **demo,
            "status": result.get("status", "failed"),
            "error": result.get("error"),
            "video_url_before": source_video_url,
            "video_url_after": None,
        }


async def main():
    parser = argparse.ArgumentParser(description="Generate demo content using GoEnhance API")
    parser.add_argument("--count", type=int, default=200, help="Number of demos to generate")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    parser.add_argument("--output", type=str, default="demos_output.json", help="Output JSON file")
    parser.add_argument("--source-video", type=str, help="Source video URL to transform")
    parser.add_argument("--batch-size", type=int, default=5, help="Concurrent API calls")
    parser.add_argument("--list-topics", action="store_true", help="List all topics and exit")

    args = parser.parse_args()

    # Just list topics
    if args.list_topics:
        topics = get_all_topics()
        print(f"\n📋 Total Topics: {len(topics)}")
        for category in DEMO_TOPICS:
            print(f"\n{category.upper()} ({len(DEMO_TOPICS[category])} topics):")
            for topic in DEMO_TOPICS[category][:3]:
                print(f"  - {topic['prompt'][:60]}...")
            if len(DEMO_TOPICS[category]) > 3:
                print(f"  ... and {len(DEMO_TOPICS[category]) - 3} more")
        print(f"\n🎨 Available Styles: {len(GOENHANCE_STYLES)}")
        for style in GOENHANCE_STYLES:
            print(f"  - [{style['id']}] {style['name']}: {style['description']}")
        return

    # Initialize client
    client = GoEnhanceClient()

    # Check credits first
    if not args.dry_run:
        await check_api_credits(client)

    # Generate combinations
    demos = generate_demo_combinations(args.count)
    print(f"\n📦 Generated {len(demos)} demo combinations")

    # Print summary by category
    categories = {}
    for demo in demos:
        cat = demo["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Sample source video (you should replace with your own)
    source_video = args.source_video or "https://cdn.goenhance.ai/user/upload-data/video-to-video/333768e610e442d02e8030693def0b6e.mp4"

    print(f"\n🎬 Source video: {source_video}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No API calls will be made")

    # Generate demos
    results = []
    for i, demo in enumerate(demos):
        result = await generate_single_demo(
            client=client,
            demo=demo,
            source_video_url=source_video,
            index=i,
            total=len(demos),
            dry_run=args.dry_run
        )
        if result:
            results.append(result)

        # Small delay between requests
        if not args.dry_run and i < len(demos) - 1:
            await asyncio.sleep(2)

    # Save results
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_count": len(results),
            "dry_run": args.dry_run,
            "source_video": source_video,
            "demos": results
        }, f, indent=2)

    print(f"\n✅ Results saved to: {output_path}")

    # Summary
    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")
    dry_run_count = sum(1 for r in results if r.get("status") == "dry_run")

    print(f"\n📊 Summary:")
    print(f"   Total: {len(results)}")
    print(f"   Completed: {completed}")
    print(f"   Failed: {failed}")
    if dry_run_count:
        print(f"   Dry run: {dry_run_count}")


if __name__ == "__main__":
    asyncio.run(main())
