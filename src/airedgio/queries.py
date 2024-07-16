import json


class Queries:
    _queries = {
        "created": {
            "query": {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "_index": "aiasset"
                                }
                            },
                            {
                                "range": {
                                    "properties.created": {
                                        "gt": "GT_TIMESTAMP",
                                        "lte": "LTE_TIMESTAMP"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },
        "changed": {
            "query": {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "_index": "aiasset"
                                }
                            },
                            {
                                "range": {
                                    "properties.changed": {
                                        "gt": "GT_TIMESTAMP",
                                        "lte": "LTE_TIMESTAMP"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },
        "by_id": {
            "query": {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "term": {
                                    "_id": "ASSET_ID"
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    _created: str
    _modified: str
    _by_id: str

    def __init__(self, queries: dict = {}) -> None:
        if queries:
            self._queries = queries

        self._created = json.dumps(self._queries['created'])
        self._modified = json.dumps(self._queries['changed'])
        self._by_id = json.dumps(self._queries['by_id'])

    def created(self, gt_timestamp: str, lte_timestamp: str) -> str:
        return (
            self
            ._created
            .replace('GT_TIMESTAMP', gt_timestamp)
            .replace('LTE_TIMESTAMP', lte_timestamp)
        )

    def modified(self, gt_timestamp: str, lte_timestamp: str) -> str:
        return (
            self
            ._modified
            .replace('GT_TIMESTAMP', gt_timestamp)
            .replace('LTE_TIMESTAMP', lte_timestamp)
        )

    def by_id(self, asset_id: str) -> str:
        return (
            self
            ._by_id
            .replace('ASSET_ID', asset_id)
        )
