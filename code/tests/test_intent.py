"""Tests for code/intent.py: eval templates, sample free text, and hand-written traps."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from intent import DELETION, NOT_APPLICABLE, classify  # noqa: E402

INTENT_SENTENCES = [
    "Please treat this message as a request for permanent account deletion.",
    "I would like to submit a request to delete this account and its personal data.",
    "I am requesting deletion of the account registered to this email address.",
    "Please erase the account linked to this email address.",
    "I am asking you to remove my account and the personal information linked to it.",
    "I no longer use this account and would like it permanently deleted.",
    "Please permanently delete the account associated with this email address.",
    "Please process a permanent account-deletion request for this email address.",
    "Please close my account and process the associated personal-data deletion.",
    "I would like the account associated with this address to be erased.",
    "Please begin the deletion process for the account using this email address.",
    "I want to close this account and have its associated personal data deleted.",
    "Solicito a exclusão permanente da conta associada a este e-mail.",
    "이 이메일 주소에 연결된 계정의 영구 삭제를 요청합니다.",
    "Solicito la eliminación permanente de la cuenta asociada a este correo.",
    "このメールアドレスに関連するアカウントの完全な削除を依頼します。",
    "Je demande la suppression définitive du compte associé à cette adresse e-mail.",
]

BOILERPLATE = [
    "Please apply the request across the systems covered by your deletion policy.",
    "Please confirm when the review is complete.",
    "Please follow the applicable retention and deletion requirements for the account.",
]

NON_DELETION = [
    "The mobile number on my profile is out of date. Please replace it with the new one and leave the account active.",
    "Please stop the promotional emails. I still need the account and my order history, so I am not asking for deletion.",
    "I'd like to download my account information in a portable format. Please keep the account as it is.",
    "I can't access my profile and need help resetting the login. Do not close the account.",
    "My surname is misspelled on the account. Can you correct it without removing any of my records?",
    "Please remove me from marketing lists only. I still want receipts and service messages for this account.",
    "Can you tell me what personal information you hold about me? This is an information request, not a request to erase it.",
    "I need a copy of last year's invoices for my records. Please leave my profile and purchase history in place.",
    "Please change the email address used for this account. I want to continue using the service.",
    "Could you send me a copy of the information held on my account? I still use it, so please don't delete or change anything.",
]

# Hand-written traps (not from the dataset).
EXTRA_NON_DELETION = [
    "No quiero eliminar mi cuenta, solo cambiar el correo.",
    "Je ne demande pas la suppression de mon compte, seulement une copie de mes données.",
    "Não quero a exclusão da conta, apenas atualizar o telefone.",
    "My account was deleted by mistake. Could you restore it?",
    "Please remove me from your mailing list.",
    "What data do you store about me?",
]
EXTRA_DELETION = [
    "Please wipe all of my personal data from your systems.",
    "I want my account closed and every trace of me removed. Backups may be kept if they cannot restore my profile.",
    "Delete my account. You can keep anonymous statistics.",
    "Please unsubscribe me and delete my account entirely.",
    "アカウントを削除してください。",
]


def _texts(name):
    with open(ROOT / "dataset" / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("sentence", INTENT_SENTENCES)
@pytest.mark.parametrize("tail", ["", " " + " ".join(BOILERPLATE[:2])])
def test_intent_sentences_are_deletion(sentence, tail):
    assert classify(sentence + tail).label == DELETION


@pytest.mark.parametrize("text", BOILERPLATE)
def test_boilerplate_alone_is_not_deletion(text):
    assert classify(text).label != DELETION


@pytest.mark.parametrize("text", NON_DELETION + EXTRA_NON_DELETION)
def test_non_deletion(text):
    assert classify(text).label == NOT_APPLICABLE, classify(text)


@pytest.mark.parametrize("text", EXTRA_DELETION)
def test_extra_deletion(text):
    assert classify(text).label == DELETION, classify(text)


def test_all_samples_are_deletion():
    wrong = [(r["case_id"], classify(r["request_text"])) for r in _texts("sample_deletion_requests.csv")
             if classify(r["request_text"]).label != DELETION]
    assert not wrong


def test_eval_counts():
    labels = [classify(r["request_text"]).label for r in _texts("deletion_requests.csv")]
    assert labels.count(DELETION) == 508
    assert labels.count(NOT_APPLICABLE) == 10
