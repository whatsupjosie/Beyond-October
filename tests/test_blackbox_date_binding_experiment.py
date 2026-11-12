"""Real cryptographic operations on generated fixtures; not a security audit."""
import pytest
pytest.importorskip('cryptography')
pytest.importorskip('zstandard')
from cryptography.exceptions import InvalidTag,InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.experiments.blackbox_date_binding import seal,unlock,change_header,parts,verify_signature,envelope

CREATED='2026-05-01T12:00:00.000Z'
ALTERED='2026-11-09T12:00:00.000Z'
RAW=b'Exact fixture: punctuation, separators | % and newlines.\n'*100


@pytest.fixture(scope='module')
def original():return seal(RAW,'cat',CREATED)


@pytest.mark.parametrize('password',['A','cat','a password with spaces','☕|,%'])
def test_arbitrary_nonempty_passwords_round_trip_exactly(password):
    blob=seal(RAW,password,CREATED)
    assert unlock(blob,password)==RAW


@pytest.mark.parametrize('field,value',[
    ('original_created_at',ALTERED),('file_id','a different file'),('raw_sha256','0'*64),
    ('compression','none')])
def test_authenticated_header_cannot_be_edited(original,field,value):
    with pytest.raises(InvalidTag):unlock(change_header(original,**{field:value}),'cat')


@pytest.mark.parametrize('date',[None,'','2026-11-09','2026-02-30T12:00:00.000Z'])
def test_missing_and_invalid_dates_are_rejected(original,date):
    with pytest.raises(ValueError):unlock(change_header(original,original_created_at=date),'cat')


def test_known_password_allows_a_new_unsigned_date(original):
    rewritten=seal(unlock(original,'cat'),'cat',ALTERED)
    assert unlock(rewritten,'cat')==RAW
    assert parts(rewritten)[0]['original_created_at']==ALTERED


def test_creation_field_cannot_be_stripped_from_the_header(original):
    header,_,ciphertext,signature,_,_=parts(original)
    del header['original_created_at']
    with pytest.raises(ValueError):unlock(envelope(header,ciphertext,signature),'cat')


def test_independent_signature_stops_rewrap_without_signing_key(original):
    trusted=Ed25519PrivateKey.generate()
    signed=seal(RAW,'cat',CREATED,trusted)
    assert verify_signature(signed,trusted.public_key())['original_created_at']==CREATED
    assert unlock(signed,'cat',trusted.public_key(),True)==RAW
    forged=seal(RAW,'cat',ALTERED,Ed25519PrivateKey.generate())
    with pytest.raises(InvalidSignature):unlock(forged,'cat',trusted.public_key(),True)
    with pytest.raises(ValueError):unlock(original,'cat',trusted.public_key(),True)
