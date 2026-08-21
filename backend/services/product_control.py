from __future__ import annotations

import hashlib
import mimetypes
from typing import Any
from uuid import UUID

from aiogram.types import BufferedInputFile
from fastapi.encoders import jsonable_encoder

from backend.core.config import Settings
from backend.db.pool import Database
from backend.domain.products import (
    LANGUAGES, MEDIA_STORAGE_TYPES, MEDIA_TYPES, PRODUCT_TYPES, RELATIONSHIP_TYPES,
    clean_benefits, clean_faq, normalize_slug, readiness_report, validate_pricing,
    validate_referral_percent,
)
from backend.repositories.product_control import ProductControlRepository


class ProductControlService:
    def __init__(self, db: Database, settings: Settings, bot: Any | None = None) -> None:
        self.db = db
        self.settings = settings
        self.bot = bot
        self.repo = ProductControlRepository()

    def _media_url(self, media_id: UUID | str | None, storage_type: str | None, value: str | None) -> str | None:
        if not value or not storage_type:
            return None
        if storage_type == "url":
            return value
        if storage_type == "object_storage" and value.startswith(("https://", "http://")):
            return value
        if storage_type == "telegram_file_id" and media_id:
            base = self.settings.public_api_base_url.rstrip("/")
            path = f"/api/public/product-media/{media_id}"
            return f"{base}{path}" if base else path
        return None

    async def list_products(self) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            rows = await self.repo.list_products(conn)
        result=[]
        for row in rows:
            item=dict(row)
            item["cover_url"] = self._media_url(row["cover_media_id"], row["cover_storage_type"], row["cover"])
            result.append(item)
        return result

    async def detail(self, *, product_id: UUID) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            product = await self.repo.get_product(conn, product_id=product_id)
            if product is None:
                raise LookupError("Product not found")
            translations = await self.repo.translations(conn, product_id=product_id)
            media = await self.repo.media(conn, product_id=product_id)
            files = await self.repo.files(conn, product_id=product_id)
            content = await self.repo.content_blocks(conn, product_id=product_id)
            relationships = await self.repo.relationships(conn, product_id=product_id)
            choices = await self.repo.catalog_choices(conn, exclude_product_id=product_id)
        media_items=[]
        for row in media:
            item=dict(row)
            item["public_url"] = self._media_url(row["id"], row["storage_type"], row["value"])
            media_items.append(item)
        return {
            "product": dict(product),
            "translations": {r["language"]: dict(r) for r in translations},
            "media": media_items,
            "files": [dict(r) for r in files],
            "content_blocks": [dict(r) for r in content],
            "relationships": [dict(r) for r in relationships],
            "catalog_choices": [dict(r) for r in choices],
            "readiness": readiness_report(product=product, translations=translations, media=media, files=files),
        }

    async def create(self, *, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        slug = normalize_slug(str(data.get("slug") or ""))
        product_type = str(data.get("product_type") or "digital_file")
        default_language = str(data.get("default_language") or "am")
        if product_type not in PRODUCT_TYPES:
            raise ValueError("Unsupported product_type")
        if default_language not in LANGUAGES:
            raise ValueError("Unsupported default_language")
        regular, recovery = validate_pricing(
            regular_price_br=data.get("regular_price_br"), recovery_price_br=data.get("recovery_price_br")
        )
        referral_percent = validate_referral_percent(data.get("referral_commission_percent", 10))
        title = str(data.get("title") or slug).strip()[:300]
        async with self.db.transaction() as conn:
            if await self.repo.get_by_slug(conn, slug=slug):
                raise ValueError("A product with this slug already exists")
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            row = await conn.fetchrow(
                """
                INSERT INTO products(slug,status,product_type,category,default_language,regular_price_br,recovery_price_br,
                    discounts_enabled,referral_enabled,referral_commission_percent,commission_only_full_price,featured,sort_order,metadata)
                VALUES($1,'draft',$2,$3,$4,$5,$6,$7,$8,$9,TRUE,$10,$11,$12::jsonb)
                RETURNING *
                """,
                slug, product_type, data.get("category"), default_language, regular, recovery,
                bool(data.get("discounts_enabled", False)), bool(data.get("referral_enabled", True)), referral_percent,
                bool(data.get("featured", False)), int(data.get("sort_order") or 0), {"created_from":"zemen_control"},
            )
            await conn.execute(
                """INSERT INTO product_translations(product_id,language,title) VALUES($1,$2,$3)""",
                row["id"], default_language, title,
            )
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.create", entity_type="product", entity_id=str(row["id"]), after=jsonable_encoder(dict(row)))
        return await self.detail(product_id=row["id"])

    async def update_core(self, *, product_id: UUID, admin_telegram_id: int, expected_revision: int, data: dict[str, Any]) -> dict[str, Any]:
        slug = normalize_slug(str(data["slug"]))
        product_type = str(data["product_type"])
        default_language = str(data["default_language"])
        if product_type not in PRODUCT_TYPES or default_language not in LANGUAGES:
            raise ValueError("Unsupported product type or language")
        regular, recovery = validate_pricing(regular_price_br=data["regular_price_br"], recovery_price_br=data.get("recovery_price_br"))
        referral_percent = validate_referral_percent(data.get("referral_commission_percent", 10))
        async with self.db.transaction() as conn:
            before = await self.repo.get_product(conn, product_id=product_id, for_update=True)
            if before is None:
                raise LookupError("Product not found")
            if int(before["revision"]) != expected_revision:
                raise ValueError("Product changed in another session. Refresh before saving.")
            conflict = await conn.fetchval("SELECT 1 FROM products WHERE slug=$1 AND id<>$2", slug, product_id)
            if conflict:
                raise ValueError("A product with this slug already exists")
            row = await conn.fetchrow(
                """
                UPDATE products SET slug=$2,product_type=$3,category=$4,default_language=$5,
                    regular_price_br=$6,recovery_price_br=$7,discounts_enabled=$8,referral_enabled=$9,
                    referral_commission_percent=$10,commission_only_full_price=TRUE,featured=$11,sort_order=$12,
                    revision=revision+1,updated_at=now()
                WHERE id=$1 RETURNING *
                """,
                product_id, slug, product_type, data.get("category"), default_language, regular, recovery,
                bool(data.get("discounts_enabled", False)), bool(data.get("referral_enabled", True)), referral_percent,
                bool(data.get("featured", False)), int(data.get("sort_order") or 0),
            )
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.update", entity_type="product", entity_id=str(product_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        return await self.detail(product_id=product_id)

    async def save_translation(self, *, product_id: UUID, language: str, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if language not in LANGUAGES:
            raise ValueError("Unsupported language")
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("Title is required")
        benefits = clean_benefits(data.get("benefits"))
        faq = clean_faq(data.get("faq"))
        expected = data.get("expected_revision")
        async with self.db.transaction() as conn:
            product = await self.repo.get_product(conn, product_id=product_id, for_update=True)
            if product is None:
                raise LookupError("Product not found")
            before = await conn.fetchrow("SELECT * FROM product_translations WHERE product_id=$1 AND language=$2 FOR UPDATE", product_id, language)
            if before is not None and expected is not None and int(before["revision"]) != int(expected):
                raise ValueError("Translation changed in another session. Refresh before saving.")
            row = await conn.fetchrow(
                """
                INSERT INTO product_translations(product_id,language,title,subtitle,short_description,description,benefits,faq)
                VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb)
                ON CONFLICT(product_id,language) DO UPDATE SET title=EXCLUDED.title,subtitle=EXCLUDED.subtitle,
                    short_description=EXCLUDED.short_description,description=EXCLUDED.description,
                    benefits=EXCLUDED.benefits,faq=EXCLUDED.faq,revision=product_translations.revision+1,updated_at=now()
                RETURNING *
                """,
                product_id, language, title, data.get("subtitle"), data.get("short_description"), data.get("description"), benefits, faq,
            )
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.translation.save", entity_type="product_translation", entity_id=f"{product_id}:{language}", before=jsonable_encoder(dict(before)) if before else None, after=jsonable_encoder(dict(row)))
        return dict(row)

    async def add_media(self, *, product_id: UUID, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        media_type = str(data.get("media_type") or "gallery")
        storage_type = str(data.get("storage_type") or "url")
        language = data.get("language")
        if media_type not in MEDIA_TYPES or storage_type not in MEDIA_STORAGE_TYPES:
            raise ValueError("Unsupported media type or storage type")
        if language not in (None, "am", "en"):
            raise ValueError("Unsupported media language")
        value = str(data.get("value") or "").strip()
        if not value:
            raise ValueError("Media value is required")
        if storage_type == "url" and not value.startswith(("https://", "http://")):
            raise ValueError("Media URL must start with http:// or https://")
        mime_type = data.get("mime_type") or mimetypes.guess_type(
            str(data.get("file_name") or value).split("?", 1)[0]
        )[0]
        async with self.db.transaction() as conn:
            if await self.repo.get_product(conn, product_id=product_id, for_update=True) is None:
                raise LookupError("Product not found")
            if media_type == "cover":
                await conn.execute("UPDATE product_media SET is_active=FALSE,updated_at=now() WHERE product_id=$1 AND media_type='cover' AND language IS NOT DISTINCT FROM $2 AND is_active=TRUE", product_id, language)
            row = await conn.fetchrow(
                """INSERT INTO product_media(product_id,language,media_type,storage_type,value,alt_text,caption,sort_order,is_active,mime_type,file_name)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,TRUE,$9,$10) RETURNING *""",
                product_id, language, media_type, storage_type, value, data.get("alt_text"), data.get("caption"), int(data.get("sort_order") or 0), mime_type, data.get("file_name"),
            )
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.media.add", entity_type="product_media", entity_id=str(row["id"]), after=jsonable_encoder(dict(row)))
        item=dict(row); item["public_url"]=self._media_url(row["id"],row["storage_type"],row["value"]); return item

    async def upload_media(self, *, product_id: UUID, admin_telegram_id: int, filename: str, content_type: str | None, data: bytes, media_type: str, language: str | None, alt_text: str | None, caption: str | None, sort_order: int) -> dict[str, Any]:
        if not self.bot or not self.settings.telegram_storage_chat_id:
            raise RuntimeError("TELEGRAM_STORAGE_CHAT_ID and a connected bot are required for dashboard uploads")
        if media_type not in MEDIA_TYPES:
            raise ValueError("Unsupported media type")
        max_bytes = self.settings.product_upload_max_mb * 1024 * 1024
        if not data or len(data) > max_bytes:
            raise ValueError(f"File must be between 1 byte and {self.settings.product_upload_max_mb} MB")
        mime_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if media_type in {"cover", "gallery", "thumbnail"} and not mime_type.startswith("image/"):
            raise ValueError(f"{media_type.title()} media must be an image")
        if media_type == "video" and not mime_type.startswith("video/"):
            raise ValueError("Video media must be a video file")
        if media_type == "preview" and not (
            mime_type.startswith(("image/", "video/")) or mime_type == "application/pdf"
        ):
            raise ValueError("Preview media must be an image, video, or PDF")

        upload = BufferedInputFile(data, filename=filename)
        storage_caption = f"Zemen product media · {product_id} · {media_type}"
        if mime_type.startswith("image/"):
            msg = await self.bot.send_photo(
                chat_id=self.settings.telegram_storage_chat_id,
                photo=upload,
                caption=storage_caption,
            )
            if not msg.photo:
                raise RuntimeError("Telegram did not return a photo file_id")
            file_id = msg.photo[-1].file_id
        elif mime_type.startswith("video/"):
            msg = await self.bot.send_video(
                chat_id=self.settings.telegram_storage_chat_id,
                video=upload,
                caption=storage_caption,
            )
            if msg.video is None:
                raise RuntimeError("Telegram did not return a video file_id")
            file_id = msg.video.file_id
        else:
            msg = await self.bot.send_document(
                chat_id=self.settings.telegram_storage_chat_id,
                document=upload,
                caption=storage_caption,
            )
            if msg.document is None:
                raise RuntimeError("Telegram did not return a document file_id")
            file_id = msg.document.file_id
        return await self.add_media(product_id=product_id, admin_telegram_id=admin_telegram_id, data={
            "media_type":media_type,"storage_type":"telegram_file_id","value":file_id,
            "language":language,"alt_text":alt_text,"caption":caption,"sort_order":sort_order,"mime_type":mime_type,
            "file_name":filename,
        })

    async def update_media(self, *, product_id: UUID, media_id: UUID, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        language = data.get("language")
        if language not in (None, "am", "en"):
            raise ValueError("Unsupported media language")
        async with self.db.transaction() as conn:
            before = await conn.fetchrow(
                "SELECT * FROM product_media WHERE id=$1 AND product_id=$2 FOR UPDATE",
                media_id,
                product_id,
            )
            if before is None:
                raise LookupError("Media not found")
            if before["media_type"] == "cover" and before["language"] != language:
                await conn.execute(
                    """UPDATE product_media SET is_active=FALSE,updated_at=now()
                       WHERE product_id=$1 AND media_type='cover'
                         AND language IS NOT DISTINCT FROM $2 AND id<>$3 AND is_active=TRUE""",
                    product_id,
                    language,
                    media_id,
                )
            row = await conn.fetchrow(
                """UPDATE product_media
                   SET language=$3,alt_text=$4,caption=$5,sort_order=$6,updated_at=now()
                   WHERE id=$1 AND product_id=$2 RETURNING *""",
                media_id,
                product_id,
                language,
                data.get("alt_text"),
                data.get("caption"),
                int(data.get("sort_order") or 0),
            )
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(
                conn,
                admin_id=admin_id,
                action="product.media.update",
                entity_type="product_media",
                entity_id=str(media_id),
                before=jsonable_encoder(dict(before)),
                after=jsonable_encoder(dict(row)),
            )
        item = dict(row)
        item["public_url"] = self._media_url(row["id"], row["storage_type"], row["value"])
        return item

    async def deactivate_media(self, *, product_id: UUID, media_id: UUID, admin_telegram_id: int) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            row = await conn.fetchrow("SELECT * FROM product_media WHERE id=$1 AND product_id=$2 FOR UPDATE", media_id, product_id)
            if row is None:
                raise LookupError("Media not found")
            changed = await conn.fetchrow("UPDATE product_media SET is_active=FALSE,updated_at=now() WHERE id=$1 RETURNING *", media_id)
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.media.deactivate", entity_type="product_media", entity_id=str(media_id), before=jsonable_encoder(dict(row)), after=jsonable_encoder(dict(changed)))
        return dict(changed)

    async def add_delivery_file(self, *, product_id: UUID, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        version = str(data.get("version") or "").strip()
        file_name = str(data.get("file_name") or "").strip()
        telegram_file_id = str(data.get("telegram_file_id") or "").strip() or None
        object_storage_key = str(data.get("object_storage_key") or "").strip() or None
        if not version or not file_name:
            raise ValueError("version and file_name are required")
        if not telegram_file_id and not object_storage_key:
            raise ValueError("A Telegram file_id or object storage key is required")
        activate = bool(data.get("activate", True))
        async with self.db.transaction() as conn:
            if await self.repo.get_product(conn, product_id=product_id, for_update=True) is None:
                raise LookupError("Product not found")
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            if activate:
                await conn.execute("UPDATE product_files SET is_active=FALSE,updated_at=now() WHERE product_id=$1 AND is_active=TRUE", product_id)
            try:
                row = await conn.fetchrow(
                    """INSERT INTO product_files(product_id,version,telegram_file_id,telegram_file_unique_id,object_storage_key,file_name,sha256,is_active,release_notes,mime_type,size_bytes,uploaded_by_admin_id)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *""",
                    product_id,version,telegram_file_id,data.get("telegram_file_unique_id"),object_storage_key,file_name,data.get("sha256"),activate,data.get("release_notes"),data.get("mime_type"),data.get("size_bytes"),admin_id,
                )
            except Exception as exc:
                if "product_files_product_id_version_key" in str(exc) or "duplicate" in str(exc).lower():
                    raise ValueError("That product version already exists") from exc
                raise
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.file.add", entity_type="product_file", entity_id=str(row["id"]), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def upload_delivery_file(self, *, product_id: UUID, admin_telegram_id: int, filename: str, content_type: str | None, data: bytes, version: str, release_notes: str | None, activate: bool) -> dict[str, Any]:
        if not self.bot or not self.settings.telegram_storage_chat_id:
            raise RuntimeError("TELEGRAM_STORAGE_CHAT_ID and a connected bot are required for dashboard uploads")
        max_bytes = self.settings.product_upload_max_mb * 1024 * 1024
        if not data or len(data) > max_bytes:
            raise ValueError(f"File must be between 1 byte and {self.settings.product_upload_max_mb} MB")
        msg = await self.bot.send_document(chat_id=self.settings.telegram_storage_chat_id, document=BufferedInputFile(data,filename=filename), caption=f"Zemen delivery · {product_id} · {version}")
        if msg.document is None:
            raise RuntimeError("Telegram did not return a document file_id")
        return await self.add_delivery_file(product_id=product_id, admin_telegram_id=admin_telegram_id, data={
            "version":version,"telegram_file_id":msg.document.file_id,"telegram_file_unique_id":msg.document.file_unique_id,
            "file_name":filename,"sha256":hashlib.sha256(data).hexdigest(),"activate":activate,"release_notes":release_notes,
            "mime_type":content_type or msg.document.mime_type,"size_bytes":len(data),
        })

    async def activate_file(self, *, product_id: UUID, file_id: UUID, admin_telegram_id: int) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            if await self.repo.get_product(conn, product_id=product_id, for_update=True) is None:
                raise LookupError("Product not found")
            target = await conn.fetchrow("SELECT * FROM product_files WHERE id=$1 AND product_id=$2 FOR UPDATE", file_id, product_id)
            if target is None:
                raise LookupError("Product file not found")
            await conn.execute("UPDATE product_files SET is_active=FALSE,updated_at=now() WHERE product_id=$1 AND is_active=TRUE", product_id)
            row = await conn.fetchrow("UPDATE product_files SET is_active=TRUE,updated_at=now() WHERE id=$1 RETURNING *", file_id)
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.file.activate", entity_type="product_file", entity_id=str(file_id), before=jsonable_encoder(dict(target)), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def save_content_block(self, *, product_id: UUID, language: str, block_key: str, audience_key: str, admin_telegram_id: int, content: dict[str, Any]) -> dict[str, Any]:
        if language not in LANGUAGES:
            raise ValueError("Unsupported language")
        block_key = block_key.strip()[:100]
        audience_key = (audience_key.strip() or "default")[:100]
        if not block_key:
            raise ValueError("block_key is required")
        async with self.db.transaction() as conn:
            if await self.repo.get_product(conn, product_id=product_id, for_update=True) is None:
                raise LookupError("Product not found")
            current = await conn.fetchrow(
                """SELECT * FROM product_content_blocks WHERE product_id=$1 AND language=$2 AND block_key=$3 AND audience_key=$4 AND is_active=TRUE ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                product_id,language,block_key,audience_key,
            )
            version = int(current["version"])+1 if current else 1
            if current:
                await conn.execute("UPDATE product_content_blocks SET is_active=FALSE,updated_at=now() WHERE id=$1", current["id"])
            row = await conn.fetchrow(
                """INSERT INTO product_content_blocks(product_id,language,block_key,audience_key,content,version,is_active)
                   VALUES($1,$2,$3,$4,$5::jsonb,$6,TRUE) RETURNING *""",
                product_id,language,block_key,audience_key,content,version,
            )
            admin_id = await self.repo.admin_id(conn, telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn, admin_id=admin_id, action="product.content.save", entity_type="product_content_block", entity_id=str(row["id"]), before=jsonable_encoder(dict(current)) if current else None, after=jsonable_encoder(dict(row)))
        return dict(row)

    async def set_relationships(self, *, product_id: UUID, admin_telegram_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized=[]
        for i,item in enumerate(items[:30]):
            kind=str(item.get("relationship_type") or "upsell")
            if kind not in RELATIONSHIP_TYPES:
                raise ValueError("Unsupported relationship type")
            target=UUID(str(item["target_product_id"]))
            if target==product_id:
                raise ValueError("A product cannot recommend itself")
            normalized.append((target,kind,int(item.get("sort_order",i))))
        async with self.db.transaction() as conn:
            if await self.repo.get_product(conn, product_id=product_id, for_update=True) is None:
                raise LookupError("Product not found")
            before=[dict(r) for r in await self.repo.relationships(conn, product_id=product_id)]
            await conn.execute("DELETE FROM product_relationships WHERE source_product_id=$1", product_id)
            for target,kind,sort_order in normalized:
                exists=await conn.fetchval("SELECT 1 FROM products WHERE id=$1",target)
                if not exists: raise ValueError("Upsell target product does not exist")
                await conn.execute("INSERT INTO product_relationships(source_product_id,target_product_id,relationship_type,sort_order) VALUES($1,$2,$3,$4)",product_id,target,kind,sort_order)
            admin_id=await self.repo.admin_id(conn,telegram_id=admin_telegram_id)
            after=[dict(r) for r in await self.repo.relationships(conn,product_id=product_id)]
            await self.repo.insert_audit(conn,admin_id=admin_id,action="product.relationships.save",entity_type="product",entity_id=str(product_id),before=jsonable_encoder(before),after=jsonable_encoder(after))
        return after

    async def set_status(self, *, product_id: UUID, admin_telegram_id: int, status: str) -> dict[str, Any]:
        if status not in {"active","hidden","archived","draft"}:
            raise ValueError("Unsupported product status")
        async with self.db.transaction() as conn:
            product=await self.repo.get_product(conn,product_id=product_id,for_update=True)
            if product is None: raise LookupError("Product not found")
            translations=await self.repo.translations(conn,product_id=product_id)
            media=await self.repo.media(conn,product_id=product_id)
            files=await self.repo.files(conn,product_id=product_id)
            readiness=readiness_report(product=product,translations=translations,media=media,files=files)
            if status=="active" and not readiness["ready"]:
                raise ValueError("Cannot publish: " + " ".join(readiness["blockers"]))
            row=await conn.fetchrow("UPDATE products SET status=$2,revision=revision+1,updated_at=now() WHERE id=$1 RETURNING *",product_id,status)
            admin_id=await self.repo.admin_id(conn,telegram_id=admin_telegram_id)
            await self.repo.insert_audit(conn,admin_id=admin_id,action=f"product.status.{status}",entity_type="product",entity_id=str(product_id),before=jsonable_encoder(dict(product)),after=jsonable_encoder(dict(row)))
        return await self.detail(product_id=product_id)
