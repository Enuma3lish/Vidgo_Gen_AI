"""
Seed Demo Examples Script
Generates sample demo examples for each topic using Leonardo AI.

Run with: python -m scripts.seed_demo_examples
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.demo import DemoExample
from app.services.leonardo import get_leonardo_client
from app.core.database import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Topics with sample prompts (30 prompts per topic)
DEMO_TOPICS = {
    "product": {
        "name_zh": "產品",
        "name_en": "Product",
        "prompts": [
            "A sleek smartphone with holographic display, floating in space, dramatic lighting",
            "Premium wireless headphones on marble surface, soft studio lighting",
            "Luxury watch with golden details, black velvet background",
            "Modern laptop on wooden desk, morning sunlight, coffee cup nearby",
            "Elegant perfume bottle with crystal reflections, purple gradient background",
            "Professional camera lens with water droplets, dramatic side lighting",
            "Smart home device on minimalist shelf, warm ambient light",
            "Gaming console with RGB lighting effects, dark room setting",
            "Wireless earbuds in charging case, clean white background",
            "Electric toothbrush on bathroom counter, fresh morning light",
            "Fitness tracker on athletic wrist, motion blur effect",
            "Portable speaker on beach sand, sunset colors",
            "Coffee machine with steam, kitchen counter setting",
            "Robot vacuum cleaner in modern living room, clean lines",
            "Smart doorbell on white door, security concept",
            "Drone hovering in sky, mountain landscape background",
            "VR headset with glowing lights, futuristic setting",
            "Electric scooter in urban environment, motion effect",
            "Mechanical keyboard with RGB backlighting, dark desk setup",
            "Wireless charger with glowing ring, minimalist design",
            "Action camera in waterproof case, underwater bubbles",
            "Smart thermostat on white wall, modern home interior",
            "Bluetooth speaker system, home entertainment setup",
            "Tablet with stylus on creative desk, art supplies around",
            "Power bank with LED indicators, travel accessories",
            "Smart scale in bathroom, health monitoring concept",
            "Wireless mouse on mousepad, professional workspace",
            "Security camera with night vision, outdoor setting",
            "Smart light bulb with color changing effect, cozy room",
            "Portable projector displaying movie, home cinema setup"
        ]
    },
    "fashion": {
        "name_zh": "時尚",
        "name_en": "Fashion",
        "prompts": [
            "Designer handbag on white pedestal, studio lighting",
            "Luxury sneakers on glass surface, dynamic angle",
            "Elegant silk dress on mannequin, soft shadows",
            "Leather wallet with gold hardware, rich textures",
            "Sunglasses on marble table, summer vibes",
            "Diamond necklace on velvet display, sparkling lights",
            "Designer belt with brand logo, premium materials",
            "High heel shoes in boutique setting, elegant display",
            "Cashmere sweater folded neatly, cozy atmosphere",
            "Sport jacket on hanger, urban background",
            "Luxury watch box presentation, gift concept",
            "Silk scarf with artistic pattern, flowing fabric",
            "Designer jeans on wooden chair, casual style",
            "Leather boots on autumn leaves, seasonal mood",
            "Pearl earrings on reflective surface, elegant lighting",
            "Vintage-style cap on rustic wood, heritage feel",
            "Formal tie with pocket square, business attire",
            "Designer backpack in urban setting, modern lifestyle",
            "Gold bracelet on wrist, close-up detail shot",
            "Wool coat on coat rack, winter fashion",
            "Athletic wear set, gym environment",
            "Luxury cufflinks on dress shirt, executive style",
            "Beaded evening clutch, party setting",
            "Canvas tote bag on beach, summer lifestyle",
            "Designer sunglasses case, travel accessories",
            "Silk pajama set on bed, luxury lifestyle",
            "Wedding dress detail shot, romantic lighting",
            "Vintage leather jacket, motorcycle aesthetic",
            "Minimalist gold ring, engagement concept",
            "Designer umbrella in rain, urban street"
        ]
    },
    "food": {
        "name_zh": "美食",
        "name_en": "Food",
        "prompts": [
            "Gourmet burger with melting cheese, steam rising",
            "Artisan coffee with latte art, cozy cafe setting",
            "Fresh sushi platter on slate, Japanese aesthetic",
            "Chocolate cake slice with berries, dessert paradise",
            "Italian pasta with fresh basil, rustic table",
            "Colorful fruit smoothie bowl, healthy breakfast",
            "Premium steak with herbs, fine dining presentation",
            "Fresh bread basket, bakery atmosphere",
            "Cocktail with ice and citrus, bar setting",
            "Pizza with stretchy cheese pull, food photography",
            "Ice cream sundae with toppings, summer treat",
            "Asian ramen bowl with steam, comfort food",
            "Fresh salad in glass bowl, healthy lifestyle",
            "Croissant with coffee, French breakfast",
            "Grilled seafood platter, ocean vibes",
            "Matcha dessert presentation, Japanese style",
            "Wine glass with vineyard background, elegant dining",
            "Fresh juice in mason jar, farm to table",
            "Tiramisu layers close-up, Italian dessert",
            "Avocado toast with eggs, brunch aesthetic",
            "BBQ ribs with sauce, American cuisine",
            "Dim sum basket with chopsticks, Chinese tradition",
            "Fresh oysters on ice, seafood luxury",
            "Pancake stack with syrup, breakfast indulgence",
            "Thai curry with rice, exotic flavors",
            "Cheese board with grapes, wine pairing",
            "Fresh donut with glaze, bakery fresh",
            "Lobster tail on plate, fine dining",
            "Bubble tea with tapioca, Asian beverage",
            "Acai bowl with granola, superfood trend"
        ]
    },
    "technology": {
        "name_zh": "科技",
        "name_en": "Technology",
        "prompts": [
            "Circuit board with glowing traces, tech abstract",
            "Server room with blue lights, data center",
            "AI robot hand reaching out, futuristic concept",
            "Holographic display interface, sci-fi technology",
            "DNA helix with digital overlay, biotech",
            "Smart city at night, connected infrastructure",
            "Quantum computer visualization, advanced computing",
            "Neural network visualization, machine learning",
            "5G tower with signal waves, connectivity",
            "Electric car charging, sustainable transport",
            "Space satellite orbiting Earth, aerospace",
            "Microchip under microscope, semiconductor",
            "Blockchain network visualization, crypto tech",
            "Smart factory with robots, Industry 4.0",
            "Augmented reality glasses view, AR technology",
            "Cloud computing concept, digital infrastructure",
            "Cybersecurity shield, digital protection",
            "3D printer creating object, additive manufacturing",
            "Solar panel array, renewable energy",
            "Autonomous vehicle sensors, self-driving",
            "Biometric scanner, security technology",
            "Wearable health device, medical tech",
            "Digital twin visualization, simulation",
            "Edge computing diagram, distributed systems",
            "Smart grid network, energy management",
            "Robotic surgery system, medical robotics",
            "Facial recognition grid, AI identification",
            "Internet of Things network, connected devices",
            "Battery cell technology, energy storage",
            "Drone swarm formation, autonomous systems"
        ]
    },
    "beauty": {
        "name_zh": "美妝",
        "name_en": "Beauty",
        "prompts": [
            "Luxury lipstick collection, makeup flatlay",
            "Skincare serum bottles, spa atmosphere",
            "Eyeshadow palette with swatches, beauty blogger",
            "Perfume with flower petals, romantic setting",
            "Mascara wand close-up, dramatic lashes",
            "Face cream jar on marble, luxury skincare",
            "Nail polish bottles in rainbow, manicure art",
            "Makeup brushes in holder, beauty station",
            "Foundation bottles with skin textures, coverage",
            "Hair care products, salon quality",
            "Lip gloss with shine effect, glossy lips",
            "Essential oil diffuser, aromatherapy",
            "Face mask application, self-care ritual",
            "Bronzer with sun glow, summer makeup",
            "Eye cream with golden particles, anti-aging",
            "Setting spray mist, makeup finish",
            "Highlighter palette, glow effect",
            "Cleansing balm texture, skincare routine",
            "Eyeliner wing close-up, precision makeup",
            "Body lotion application, moisturizing",
            "Blush compact with mirror, on-the-go beauty",
            "Vitamin C serum, brightening skincare",
            "Makeup sponge collection, blending tools",
            "Sunscreen bottle on beach, sun protection",
            "Retinol night cream, anti-aging routine",
            "Brow gel application, defined brows",
            "Sheet mask on face, Korean skincare",
            "Primer drops on skin, makeup prep",
            "Concealer under eye, flawless coverage",
            "Toner essence splash, hydrating skincare"
        ]
    },
    "home": {
        "name_zh": "居家",
        "name_en": "Home",
        "prompts": [
            "Modern sofa in living room, interior design",
            "Kitchen island with pendant lights, culinary space",
            "Bedroom with natural light, cozy morning",
            "Bathroom with freestanding tub, spa luxury",
            "Home office setup, work from home",
            "Dining table with flowers, dinner party",
            "Bookshelf styling, literary corner",
            "Outdoor patio furniture, garden living",
            "Smart home control panel, connected living",
            "Laundry room organization, clean space",
            "Kids playroom design, fun colors",
            "Wine cellar display, connoisseur storage",
            "Walk-in closet organization, wardrobe goals",
            "Home gym equipment, fitness space",
            "Art gallery wall, curated collection",
            "Minimalist entryway, first impressions",
            "Cozy reading nook, book lover retreat",
            "Modern fireplace, warm ambiance",
            "Indoor plants arrangement, urban jungle",
            "Smart lighting system, mood setting",
            "Luxury bed linens, hotel quality",
            "Open concept kitchen, modern layout",
            "Home theater setup, entertainment room",
            "Zen garden corner, meditation space",
            "Pet-friendly living room, fur baby home",
            "Scandinavian design bedroom, Nordic style",
            "Industrial loft space, urban living",
            "Coastal style decor, beach house vibes",
            "Bohemian living room, eclectic style",
            "Contemporary bathroom design, modern fixtures"
        ]
    },
    "sports": {
        "name_zh": "運動",
        "name_en": "Sports",
        "prompts": [
            "Running shoes on track, athletic performance",
            "Basketball in motion, action shot",
            "Golf club and ball, precision sport",
            "Tennis racket on court, game ready",
            "Swimming goggles by pool, aquatic sports",
            "Yoga mat with accessories, mindfulness",
            "Cycling helmet and bike, road cycling",
            "Boxing gloves on ring, combat sports",
            "Soccer ball on field, team sports",
            "Gym weights and equipment, strength training",
            "Surfboard on beach, ocean sports",
            "Skiing equipment in snow, winter sports",
            "Hiking boots on trail, outdoor adventure",
            "Fitness tracker on wrist, workout data",
            "Protein shake and supplements, nutrition",
            "Rock climbing gear, extreme sports",
            "Skateboard on ramp, street culture",
            "Martial arts uniform, discipline",
            "Dance shoes in studio, performance art",
            "Kayak on river, water adventure",
            "Table tennis paddle, precision game",
            "Archery bow and arrows, target practice",
            "Cricket bat and ball, classic sport",
            "Volleyball on sand, beach sports",
            "Horse riding equipment, equestrian",
            "Badminton racket, indoor sport",
            "Roller skates neon lights, retro fitness",
            "Fencing mask and sword, elegant combat",
            "CrossFit equipment, functional fitness",
            "Triathlon gear set, endurance challenge"
        ]
    },
    "travel": {
        "name_zh": "旅遊",
        "name_en": "Travel",
        "prompts": [
            "Luxury suitcase in airport, jet setter",
            "Passport with boarding pass, adventure awaits",
            "Beach resort poolside, tropical vacation",
            "Mountain cabin with view, nature retreat",
            "City skyline at sunset, urban exploration",
            "Camera with travel photos, photography journey",
            "Airplane window view, flying high",
            "Hotel room with ocean view, luxury stay",
            "Vintage train journey, romantic travel",
            "Travel journal and map, wanderlust",
            "Yacht on blue sea, sailing adventure",
            "Hot air balloon at dawn, aerial view",
            "Safari jeep in savanna, wildlife adventure",
            "Ancient temple exploration, cultural discovery",
            "Northern lights sky, arctic wonder",
            "Beach hammock at sunset, relaxation",
            "Tokyo street at night, urban Asia",
            "Swiss alps panorama, mountain majesty",
            "Greek island blue domes, Mediterranean beauty",
            "Desert camp under stars, nomadic experience",
            "Rainforest waterfall, tropical wonder",
            "Cruise ship deck, ocean voyage",
            "Parisian cafe scene, European charm",
            "Bali rice terraces, Southeast Asia",
            "New York Times Square, city lights",
            "Maldives overwater villa, paradise found",
            "Iceland ice cave, frozen wonder",
            "Australian outback sunset, down under",
            "Venice canal gondola, Italian romance",
            "Morocco market colors, cultural immersion"
        ]
    }
}


async def seed_demo_examples(
    count_per_topic: int = 30,
    generate_videos: bool = False
):
    """
    Seed demo examples for all topics.

    Args:
        count_per_topic: Number of examples per topic (max 30)
        generate_videos: Whether to generate videos (slower, more costly)
    """
    # Create database connection
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    leonardo = get_leonardo_client()

    async with async_session() as db:
        for topic, topic_data in DEMO_TOPICS.items():
            logger.info(f"Seeding topic: {topic}")

            prompts = topic_data["prompts"][:count_per_topic]

            for i, prompt in enumerate(prompts):
                logger.info(f"  [{i+1}/{len(prompts)}] Generating: {prompt[:50]}...")

                try:
                    if generate_videos:
                        # Full pipeline: image + video
                        result = await leonardo.generate_product_video(
                            prompt=prompt,
                            model="phoenix",
                            motion_strength=5,
                            timeout=300
                        )
                    else:
                        # Image only (faster for seeding)
                        result = await leonardo.generate_image_and_wait(
                            prompt=prompt,
                            model="phoenix",
                            timeout=120
                        )

                    if result.get("success"):
                        # Create demo example
                        example = DemoExample(
                            topic=topic,
                            topic_zh=topic_data["name_zh"],
                            topic_en=topic_data["name_en"],
                            prompt=prompt,
                            prompt_enhanced=prompt,
                            image_url=result.get("image_url"),
                            video_url=result.get("video_url"),
                            title=prompt[:100],
                            title_zh=None,
                            title_en=prompt[:100],
                            style_tags=[topic, "product", "advertising"],
                            source_service="leonardo",
                            is_active=True
                        )
                        db.add(example)
                        await db.commit()
                        logger.info(f"    Created example: {example.id}")
                    else:
                        logger.error(f"    Failed: {result.get('error')}")

                except Exception as e:
                    logger.error(f"    Error: {e}")

                # Rate limiting
                await asyncio.sleep(2)

    logger.info("Seeding complete!")


async def seed_placeholder_examples():
    """
    Seed placeholder examples without generating images.
    Uses placeholder URLs for testing.
    """
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Create tables if they don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        for topic, topic_data in DEMO_TOPICS.items():
            logger.info(f"Seeding placeholder topic: {topic}")

            prompts = topic_data["prompts"]

            for i, prompt in enumerate(prompts):
                # Create demo example with placeholder URLs
                example = DemoExample(
                    topic=topic,
                    topic_zh=topic_data["name_zh"],
                    topic_en=topic_data["name_en"],
                    prompt=prompt,
                    prompt_enhanced=prompt,
                    image_url=f"https://picsum.photos/seed/{topic}_{i}/800/600",
                    video_url=None,
                    title=prompt[:100],
                    title_zh=None,
                    title_en=prompt[:100],
                    style_tags=[topic, "product", "advertising"],
                    source_service="placeholder",
                    is_active=True
                )
                db.add(example)

            await db.commit()
            logger.info(f"  Added {len(prompts)} placeholders for {topic}")

    logger.info("Placeholder seeding complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed demo examples")
    parser.add_argument("--placeholder", action="store_true", help="Use placeholder images (no API calls)")
    parser.add_argument("--videos", action="store_true", help="Generate videos (slower)")
    parser.add_argument("--count", type=int, default=30, help="Examples per topic")

    args = parser.parse_args()

    if args.placeholder:
        asyncio.run(seed_placeholder_examples())
    else:
        asyncio.run(seed_demo_examples(count_per_topic=args.count, generate_videos=args.videos))
