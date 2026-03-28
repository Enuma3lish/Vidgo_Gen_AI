# Example Generation Flow Documentation

**Date**: March 27, 2026
**Environment**: GCP Production (vidgo-backend-38714015566.asia-east1.run.app)
**Status**: Current implementation with OLD pricing system

## Overview

This document describes the current example generation flow for the VidGo AI platform. The system uses a dual-mode architecture:
1. **Demo/Preset Mode**: For visitors and free users (watermarked results)
2. **Subscriber Mode**: For paid users (full-quality results with credits)

## Current System Architecture

### API Endpoints
- **Base URL**: `https://vidgo-backend-38714015566.asia-east1.run.app`
- **API Version**: `/api/v1`
- **Pricing System**: OLD pricing system (demo, starter, pro, pro_plus plans)

### Available Tools
1. Background Removal (`/tools/remove-bg`)
2. Product Scene (`/tools/product-scene`)
3. AI Try-On (`/tools/try-on`)
4. Room Redesign (`/tools/room-redesign`)
5. Short Video (`/tools/short-video`)
6. AI Avatar (`/tools/avatar`)
7. Effects (`/effects/apply-style`)
8. Pattern Generate (`/tools/pattern-generate`)

## Example Generation Flow for Each Tool

### 1. Background Removal Example Flow

**Demo User Flow**:
```
1. GET /api/v1/demo/presets/background_removal?limit=1
   → Returns: { "presets": [{ "id": "preset_1", "image_url": "...", "prompt": "..." }] }

2. POST /api/v1/demo/use-preset
   Body: { "tool_id": "background_removal", "preset_id": "preset_1" }
   → Returns: { "result_url": "watermarked_image.jpg", "watermarked": true }
   
3. Attempt download → Blocked with "Subscribe for Full Access" message
```

**Subscriber Flow**:
```
1. POST /api/v1/tools/remove-bg
   Body: { "image_url": "user_uploaded_image.jpg" }
   Headers: { "Authorization": "Bearer <token>" }
   
2. Credit check: 3 credits deducted from balance
3. API call: PiAPI background removal service
4. Result saved to UserGenerations table
5. Returns: { "result_url": "clean_image.png", "generation_id": "uuid", "credits_used": 3 }
```

### 2. Product Scene Example Flow

**Demo User Flow**:
```
1. GET /api/v1/demo/presets/product_scene?limit=1
   → Returns: { "presets": [{ "id": "scene_1", "scene_type": "luxury", ... }] }

2. POST /api/v1/demo/use-preset
   Body: { "tool_id": "product_scene", "preset_id": "scene_1" }
   → Returns: { "result_url": "watermarked_composite.jpg", "watermarked": true }
```

**Subscriber Flow**:
```
1. POST /api/v1/tools/product-scene
   Body: { 
     "image_url": "product_image.jpg",
     "scene_type": "luxury"  // studio, nature, luxury, minimal, lifestyle, beach, urban, garden
   }
   
2. Pipeline:
   a. Remove background (3 credits)
   b. Generate scene with T2I model (5 credits)
   c. Composite with PIL (2 credits)
   Total: 10 credits
   
3. Returns: { "result_url": "composite_scene.jpg", "credits_used": 10 }
```

### 3. AI Try-On Example Flow

**Demo User Flow**:
```
1. GET /api/v1/demo/presets/try_on?limit=1
   → Returns: { "presets": [{ "model_id": "male_model_1", "garment_url": "..." }] }

2. POST /api/v1/demo/use-preset
   Body: { "tool_id": "try_on", "preset_id": "preset_1" }
   → Returns: { "result_url": "watermarked_tryon.jpg", "watermarked": true }
```

**Subscriber Flow**:
```
1. POST /api/v1/tools/try-on
   Body: {
     "model_image_url": "user_model.jpg",  // OR "model_id": "male_model_1"
     "garment_image_url": "garment.jpg"
   }
   
2. API: PiAPI specialized try-on service
3. Credits: 15 credits
4. Returns: { "result_url": "tryon_result.jpg", "credits_used": 15 }
```

### 4. Room Redesign Example Flow

**Demo User Flow**:
```
1. GET /api/v1/demo/presets/room_redesign?limit=1
   → Returns: { "presets": [{ "room_type": "living_room", "style_id": "modern" }] }

2. POST /api/v1/demo/use-preset
   Body: { "tool_id": "room_redesign", "preset_id": "preset_1" }
   → Returns: { "result_url": "watermarked_redesign.jpg", "watermarked": true }
```

**Subscriber Flow**:
```
1. POST /api/v1/tools/room-redesign
   Body: {
     "image_url": "room_photo.jpg",
     "style_id": "modern",  // modern, traditional, minimalist, industrial, scandinavian
     "room_type": "living_room"  // living_room, bedroom, kitchen, bathroom, office
   }
   
2. API: PiAPI (Wan Doodle) — no fallback
3. Credits: 20 credits
4. Returns: { "result_url": "redesigned_room.jpg", "credits_used": 20 }
```

### 5. Short Video Example Flow

**Demo User Flow**:
```
1. GET /api/v1/demo/presets/short_video?limit=1
   → Returns: { "presets": [{ "video_url": "demo_video.mp4", "duration": 5 }] }

2. Play demo video directly (no generation)
```

**Subscriber Flow**:
```
1. POST /api/v1/tools/short-video
   Body: {
     "image_url": "input_image.jpg",
     "motion_strength": 0.7,  // 0.1 to 1.0
     "style": "cinematic",  // optional
     "script": "A beautiful product showcase",  // optional
     "voice_id": "en_female_1"  // optional
   }
   
2. API: PiAPI I2V (Image to Video) — no fallback
3. Credits: 25-35 credits (based on complexity)
4. Returns: { "result_url": "generated_video.mp4", "duration": 5, "credits_used": 30 }
```

### 6. AI Avatar Example Flow

**Demo User Flow**:
```
1. GET /api/v1/demo/presets/ai_avatar?limit=1
   → Returns: { "presets": [{ "avatar_id": "avatar_1", "script_id": "welcome" }] }

2. Play demo avatar video
```

**Subscriber Flow**:
```
1. POST /api/v1/tools/avatar
   Body: {
     "image_url": "user_photo.jpg",
     "script": "Welcome to our platform!",
     "language": "en",  // en, zh-TW, ja, ko
     "voice_id": "en_male_1",
     "aspect_ratio": "16:9",
     "resolution": "1080p"
   }
   
2. API: PiAPI avatar generation
3. Credits: 30 credits
4. Returns: { "result_url": "avatar_video.mp4", "duration": 10, "credits_used": 30 }
```

### 7. Effects Example Flow

**Demo User Flow**:
```
1. GET /api/v1/effects/styles
   → Returns: { "styles": [{ "id": "anime", "name": "Anime Style", "demo_url": "..." }] }

2. POST /api/v1/demo/use-preset
   Body: { "tool_id": "effect", "preset_id": "anime" }
   → Returns: { "result_url": "watermarked_effect.jpg", "watermarked": true }
```

**Subscriber Flow**:
```
1. POST /api/v1/effects/apply-style
   Body: {
     "image_url": "input_image.jpg",
     "style_id": "anime"  // anime, oil_painting, sketch, watercolor, etc.
   }
   
2. Credits: 8 credits
3. Returns: { "result_url": "styled_image.jpg", "credits_used": 8 }
```

## Credit System Flow

### Credit Deduction Priority
1. **Bonus credits** (from referrals, promotions)
2. **Subscription credits** (monthly allocation)
3. **Purchased credits** (one-time purchases)

### Credit Costs (OLD Pricing System)
- Background Removal: 3 credits
- Product Scene: 10 credits
- AI Try-On: 15 credits
- Room Redesign: 20 credits
- Short Video: 25-35 credits
- AI Avatar: 30 credits
- Effects: 8 credits
- HD Enhance: 12 credits
- Video Enhance: 15 credits

## Authentication Flow

### User Registration
```
POST /api/v1/auth/register
Body: {
  "email": "user@example.com",
  "password": "Password123!",
  "password_confirm": "Password123!"
}
→ Returns: { "user_id": "uuid", "message": "Verification email sent" }
```

### Email Verification
```
GET /api/v1/auth/verify-email?token=<verification_token>
→ Returns: { "success": true, "message": "Email verified" }
```

### Login
```
POST /api/v1/auth/login
Body: {
  "email": "user@example.com",
  "password": "Password123!"
}
→ Returns: { "access_token": "jwt_token", "token_type": "bearer" }
```

## Current Limitations

### OLD Pricing System
- Plans: demo, starter, pro, pro_plus
- No model selection (only "default" model)
- Basic concurrent limits (1 for starter, 2 for pro, 3 for pro_plus)
- No premium model access (wan_pro, gemini_pro)

### Missing NEW Pricing Features
- Model selection interface
- Plan permission checking (`/plans/check-permission` returns 404)
- Concurrent limit checking (`/plans/check-concurrent` returns 404)
- Plan comparison table (`/plans/comparison` returns 404)

## Testing Examples

### Test 1: Demo User Background Removal
```bash
curl -X GET "https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/demo/presets/background_removal?limit=1"
```

### Test 2: Subscriber Background Removal (with auth)
```bash
curl -X POST "https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/tools/remove-bg" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/product.jpg"}'
```

### Test 3: Check Service Pricing
```bash
curl -X GET "https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/credits/pricing"
```

### Test 4: Check OLD Pricing Plans
```bash
curl -X GET "https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/subscriptions/plans"
```

## Future Enhancements

### NEW Pricing System Integration
When the NEW pricing system is deployed:
1. Model selection will be available
2. Plan-based permission checking
3. Concurrent generation limits
4. Premium model access (wan_pro, gemini_pro)

### Enhanced Example Generation
1. More diverse preset examples
2. Better material pre-generation
3. Improved demo experience
4. Gallery integration with real-time generation

## Conclusion

The current example generation flow is functional with the OLD pricing system. Users can:
- Browse demo examples without registration
- Test tools with watermarked results
- Subscribe for full access with credits
- Generate custom content with basic models

The system is ready for user testing, with the NEW pricing system partially implemented and awaiting full deployment.