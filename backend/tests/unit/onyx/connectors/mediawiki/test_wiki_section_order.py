import datetime
from unittest.mock import MagicMock

import pytest
import pywikibot
from pytest_mock import MockFixture

from onyx.configs.constants import DocumentSource
from onyx.connectors.mediawiki.wiki import MediaWikiConnector, get_doc_from_page
from onyx.connectors.wikipedia.connector import WikipediaConnector


@pytest.fixture
def offline_page(mocker: MockFixture) -> MagicMock:
    """Mock wiki I/O while keeping the real section parser and Document model."""
    mocker.patch(
        "pywikibot.comms.http.request",
        side_effect=AssertionError("Section conversion must not use the network"),
    )

    site = mocker.MagicMock(spec=pywikibot.site.APISite)
    site.namespaces = {14: ["Category"]}
    site.validLanguageLinks.return_value = ["en", "de"]
    site.family.obsolete = {}

    page = mocker.MagicMock(spec=pywikibot.Page)
    page.site = site
    page.full_url.return_value = "https://wiki.example.test/Test_Page"
    page.title.return_value = "Test Page"
    page.pageid = 42
    page.latest_revision.timestamp = pywikibot.Timestamp(
        2026,
        1,
        1,
        tzinfo=datetime.timezone.utc,
    )

    category = mocker.MagicMock(spec=pywikibot.Category)
    category.title.return_value = "Category:Testing"
    page.categories.return_value = [category]

    return page


@pytest.mark.parametrize(
    "source_type",
    [
        MediaWikiConnector.document_source_type,
        WikipediaConnector.document_source_type,
    ],
    ids=["mediawiki", "wikipedia"],
)
@pytest.mark.parametrize(
    ("page_text", "expected_texts", "expected_anchors"),
    [
        pytest.param(
            "Introduction\n== First section ==\nFirst body\n"
            "=== Second section ===\nSecond body",
            [
                "Introduction\n",
                "== First section ==\nFirst body\n",
                "=== Second section ===\nSecond body",
            ],
            ["", "#First_section", "#Second_section"],
            id="introduction-and-nested-sections",
        ),
        pytest.param(
            "Introduction only",
            ["Introduction only"],
            [""],
            id="no-headings",
        ),
        pytest.param(
            "== First section ==\nFirst body",
            ["", "== First section ==\nFirst body"],
            ["", "#First_section"],
            id="empty-introduction",
        ),
        pytest.param(
            "",
            [""],
            [""],
            id="empty-page",
        ),
    ],
)
def test_get_doc_from_page_preserves_source_order(
    offline_page: MagicMock,
    source_type: DocumentSource,
    page_text: str,
    expected_texts: list[str],
    expected_anchors: list[str],
) -> None:
    offline_page.text = page_text

    document = get_doc_from_page(
        offline_page,
        offline_page.site,
        source_type,
    )

    assert [section.text for section in document.sections] == expected_texts
    assert [section.link for section in document.sections] == [
        f"https://wiki.example.test/Test_Page{anchor}" for anchor in expected_anchors
    ]
    assert document.get_text_content() == " ".join(
        text for text in expected_texts if text
    )
    assert document.source == source_type
    assert document.title == "Test Page"
    assert document.semantic_identifier == "Test Page"
    assert document.metadata == {
        "categories": ["Category:Testing"],
    }
    assert document.id == "MEDIAWIKI_42_https://wiki.example.test/Test_Page"
    assert document.doc_updated_at == datetime.datetime(
        2026,
        1,
        1,
        tzinfo=datetime.timezone.utc,
    )
