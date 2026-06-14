import asyncio
import sys
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.material import Material

async def verify():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(Material.id)))
        count = result.scalar()
        print(f"Total Materials in DB: {count}")
        
        # Get latest material
        result = await db.execute(select(Material).order_by(Material.created_at.desc()).limit(1))
        latest = result.scalars().first()
        if latest:
            print(f"Latest Material: {latest.topic} ({latest.tool_type})")
            print(f"  - Image: {latest.result_image_url}")
            print(f"  - Status: {latest.status}")
        else:
            print("No materials found!")

if __name__ == "__main__":
    asyncio.run(verify())
