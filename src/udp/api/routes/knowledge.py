"""Universal Downloader Pro — API routes: knowledge base."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from udp.models.db import Session, KnowledgeDomain

bp = Blueprint("knowledge", __name__)


@bp.get("/api/knowledge")
def list_knowledge():
    q = (request.args.get("q") or "").strip().lower()
    cms = (request.args.get("cms") or "").strip().lower()
    site_type = (request.args.get("site_type") or "").strip().lower()
    with Session() as session:
        query = session.query(KnowledgeDomain)
        results = []
        for d in query.all():
            if q and q not in d.domain.lower():
                continue
            if cms and (d.cms or "").lower() != cms:
                continue
            if site_type and (d.site_type or "").lower() != site_type:
                continue
            results.append({
                "domain": d.domain,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "archives": d.archives,
                "category": d.category,
                "cms": d.cms,
                "site_type": d.site_type,
                "notes": d.notes,
                "asset_counts": __import__("json").loads(d.asset_counts or "{}"),
            })
    return jsonify({"domains": results, "count": len(results)})


@bp.delete("/api/knowledge/<domain>")
def delete_knowledge(domain: str):
    with Session() as session:
        row = session.get(KnowledgeDomain, domain)
        if not row:
            return jsonify({"error": "not found"}), 404
        session.delete(row)
        session.commit()
    return jsonify({"deleted": domain})
