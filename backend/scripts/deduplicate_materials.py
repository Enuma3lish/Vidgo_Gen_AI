
import asyncio
import logging
import sys
import os

# Add app to path
sys.path.insert(0, os.getcwd())

from sqlalchemy import select, func, delete
from app.core.database import AsyncSessionLocal
from app.models.material import Material

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def deduplicate_materials():
    """
    Remove duplicate materials from the database.
    Keeps the one with the highest quality_score or most recent update.
    """
    logger.info("Starting material deduplication...")
    
    async with AsyncSessionLocal() as session:
        # 1. Find duplicate hashes
        # Group by lookup_hash and count
        query = (
            select(Material.lookup_hash, func.count(Material.id))
            .group_by(Material.lookup_hash)
            .having(func.count(Material.id) > 1)
        )
        
        result = await session.execute(query)
        duplicates = result.all()
        
        if not duplicates:
            logger.info("No duplicates found.")
            return

        logger.info(f"Found {len(duplicates)} sets of duplicates.")
        
        total_deleted = 0
        
        for lookup_hash, count in duplicates:
            if not lookup_hash:
                continue
                
            # Get all materials with this hash
            m_query = (
                select(Material)
                .where(Material.lookup_hash == lookup_hash)
                .order_by(Material.quality_score.desc(), Material.updated_at.desc())
            )
            
            m_result = await session.execute(m_query)
            materials = m_result.scalars().all()
            
            # Keep the first one (best quality or newest), delete others
            to_keep = materials[0]
            to_delete = materials[1:]
            
            logger.info(f"Hash {lookup_hash[:8]}...: Keeping {to_keep.id}, deleting {len(to_delete)} duplicates")
            
            for m in to_delete:
                await session.delete(m)
                total_deleted += 1
                
        await session.commit()
        logger.info(f"Deduplication complete. Deleted {total_deleted} materials.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(deduplicate_materials())
