# VidGo AI - Changelog

All notable changes to this project will be documented in this file.

---

## [2024-12-28] - Major Backend Refactoring for Demo Tier

### Summary
Refactored backend to support efficient demo tier with prompt caching, similarity matching, and content moderation.

### Changes Made

#### 1. Image/Video Generation Service
- **Changed**: Replaced GoEnhance API with Leonardo AI API
- **API Key**: `LEONARDO_API_KEY` configured in `.env`
- **Reason**: Better quality and cost efficiency for demo examples

#### 2. Database Schema Updates
- **Added Table**: `demo_examples` - Pre-generated examples for inspiration gallery
  - Fields: `id`, `topic`, `prompt`, `prompt_enhanced`, `image_url`, `video_url`, `created_at`
- **Added Table**: `prompt_cache` - Cache for user prompts and results
  - Fields: `id`, `prompt_original`, `prompt_normalized`, `prompt_embedding`, `image_url`, `video_url`, `usage_count`, `created_at`
- **Added Index**: GIN index on `prompt_embedding` for fast similarity search

#### 3. New Services
- **Leonardo Service** (`app/services/leonardo.py`)
  - `generate_image()` - Generate image from prompt
  - `generate_video()` - Generate video from image

- **Gemini Service** (`app/services/gemini_service.py`)
  - `enhance_prompt()` - Improve user prompts for better results
  - `moderate_content()` - Detect illegal/18+ content
  - `get_prompt_embedding()` - Generate embedding for similarity matching

- **Similarity Service** (`app/services/similarity.py`)
  - `find_similar_prompt()` - Find cached results for similar prompts
  - `calculate_similarity()` - Cosine similarity calculation
  - Threshold: 0.85 similarity = use cached result

#### 4. API Endpoints Updated
- **GET `/api/v1/demo/inspiration`** - Returns 10 random examples from database
- **POST `/api/v1/demo/generate`** - Enhanced flow:
  1. Moderate content (reject illegal/18+)
  2. Enhance prompt with Gemini
  3. Check for similar cached prompts
  4. If similar found (>85%), return cached result
  5. If not found, generate new and cache result

#### 5. Frontend Updates
- **Renamed**: "Product Video" → "Product Ads Video"
- **Updated**: Inspiration gallery now loads from backend API
- **Added**: Loading states and error handling

#### 6. Demo Tier Specifications
| Feature | Demo Tier |
|---------|-----------|
| Credits | 2 (1 image + 1 video) |
| Resolution | 720p |
| Watermark | Yes |
| Content Moderation | Enabled |
| Prompt Enhancement | Enabled |
| Similarity Caching | Enabled |

#### 7. Pre-generated Examples
- **Topics**: Product, Fashion, Food, Technology, Beauty, Home, Sports, Travel
- **Count**: 30 examples per topic (240 total)
- **Storage**: PostgreSQL `demo_examples` table

### Time Cost Estimate
| Task | Estimated Time |
|------|----------------|
| Database schema updates | 30 min |
| Leonardo service | 1 hour |
| Gemini service | 1 hour |
| Similarity matching | 45 min |
| API endpoints | 1 hour |
| Generate examples | 2 hours |
| Frontend updates | 30 min |
| Testing | 1 hour |
| **Total** | **~8 hours** |

### Configuration Required
```env
# Leonardo AI
LEONARDO_API_KEY=8c1bd967-e9ff-406a-bac2-331e4e74e25c

# Gemini (for prompt enhancement & moderation)
GEMINI_API_KEY=your_gemini_api_key
```

### Migration Commands
```bash
# Generate migration
docker exec vidgo_backend alembic revision --autogenerate -m "add_demo_examples_and_prompt_cache"

# Apply migration
docker exec vidgo_backend alembic upgrade head
```

---

## [2024-12-28] - Promotion System Added

### Changes Made
- Added `promotions` table for managing sales events (11/11, 12/12, etc.)
- Added `credit_packages` table for purchasable credit bundles
- Added `promotion_usages` table for tracking usage
- Created promotion API endpoints (`/api/v1/promotions/*`)

### Pricing Structure (NT$)
| Tier | Monthly | Credits |
|------|---------|---------|
| Demo | $0 | 2 |
| Starter | NT$299 | 80 |
| Pro | NT$599 | 150 |
| Unlimited | NT$999 | 450 |

---

## [2024-12-28] - Frontend Redesign

### Changes Made
- Main focus: Product Ads Video creation
- Added 5-language support (中文, English, 日本語, 한국어, Español)
- Added login/register functionality
- Added inspiration gallery with category filters
- Added style tags for filtering

---
