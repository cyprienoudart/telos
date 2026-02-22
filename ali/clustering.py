"""
K-Means Clustering (Component 2) — Groups related elements together.
Allows the RL question generator to target clusters instead of individual elements,
enabling multi-element questions that cover more ground per turn.
"""
from __future__ import annotations

from typing import Optional


class ElementClusterer:
    """
    Component 2: Clusters related elements so the question generator
    can ask one question that covers multiple related elements.
    
    For hackathon: uses hardcoded semantic groupings (fast, no model needed).
    For production: would use sentence-transformers + sklearn KMeans.
    """

    # Semantic groupings — which elements naturally go together
    CLUSTER_RULES = {
        "design_and_brand": [
            "design_style", "existing_branding", "color_preferences",
            "design_direction", "style_references", "typography_preferences",
            "visual_assets", "visual_assets_needed",
        ],
        "audience_and_reach": [
            "target_audience", "target_market", "target_customers",
            "target_users", "existing_audience_size", "audience_size",
        ],
        "content_and_messaging": [
            "content_ready", "key_message", "messaging_tone", "brand_tone",
            "brand_voice", "brand_personality", "topics_themes",
            "seo_keywords", "seo_requirements",
        ],
        "technical_setup": [
            "tech_platform", "platform_preference", "platform",
            "domain_hosting", "integrations", "tech_stack",
            "existing_backend", "data_sources",
        ],
        "scope_and_deliverables": [
            "pages_structure", "core_features", "deliverables",
            "content_type", "campaign_channels", "promotion_channel",
            "visualization_types", "filtering_drilldown",
        ],
        "business_and_logistics": [
            "timeline", "budget", "budget_range", "campaign_dates",
            "campaign_duration", "success_metrics", "approval_process",
            "maintenance_plan",
        ],
        "offer_and_commerce": [
            "offer_promotion", "offer_incentive", "pricing_strategy",
            "payment_methods", "shipping_logistics", "monetization",
            "products_services", "product_catalog_size",
        ],
    }

    def cluster(self, elements: list[dict]) -> list[dict]:
        """
        Cluster elements into groups.

        Args:
            elements: List of element dicts with name, score, status

        Returns:
            List of cluster dicts:
            {
                "cluster_name": str,
                "elements": [element dicts],
                "total_score": int (of undefined elements only),
                "undefined_count": int,
                "all_answered": bool
            }
        """
        # Assign each element to a cluster
        element_to_cluster = {}
        for cluster_name, member_names in self.CLUSTER_RULES.items():
            for member in member_names:
                element_to_cluster[member] = cluster_name

        # Build clusters
        clusters = {}
        unclustered = []

        for elem in elements:
            cluster_name = element_to_cluster.get(elem["name"])
            if cluster_name:
                if cluster_name not in clusters:
                    clusters[cluster_name] = []
                clusters[cluster_name].append(elem)
            else:
                unclustered.append(elem)

        # If there are unclustered elements, group them as "other"
        if unclustered:
            clusters["other"] = unclustered

        # Build result with scores
        result = []
        for cluster_name, cluster_elements in clusters.items():
            undefined = [e for e in cluster_elements if e["status"] == "undefined"]
            result.append({
                "cluster_name": cluster_name,
                "elements": cluster_elements,
                "total_score": sum(e["score"] for e in undefined),
                "undefined_count": len(undefined),
                "all_answered": len(undefined) == 0,
            })

        # Sort by total undefined score (highest first)
        result.sort(key=lambda c: c["total_score"], reverse=True)
        return result

    def get_best_cluster(self, clusters: list[dict]) -> Optional[dict]:
        """Get the cluster with the highest undefined score."""
        for cluster in clusters:
            if not cluster["all_answered"]:
                return cluster
        return None

    def get_cluster_elements_for_question(self, cluster: dict) -> list[dict]:
        """Get the undefined elements in a cluster, sorted by score."""
        undefined = [e for e in cluster["elements"] if e["status"] == "undefined"]
        undefined.sort(key=lambda e: e["score"], reverse=True)
        return undefined
