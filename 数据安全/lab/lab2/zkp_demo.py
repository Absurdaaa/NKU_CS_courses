import hashlib
import json
import secrets
from dataclasses import asdict, dataclass


P = 1019
Q = 509
G = 3


def equation(x: int) -> int:
    return x**3 + x + 5


def hash_to_scalar(*parts: int) -> int:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part).encode("utf-8"))
        h.update(b"|")
    return int.from_bytes(h.digest(), "big") % Q


def find_integer_solutions(out: int, low: int = -100, high: int = 100) -> list[int]:
    return [x for x in range(low, high + 1) if equation(x) == out]


@dataclass
class Proof:
    out: int
    public_key: int
    commitment: int
    response: int


def generate_proof(out: int, witness: int) -> Proof:
    if equation(witness) != out:
        raise ValueError("给定 witness 不满足方程约束")

    nonce = secrets.randbelow(Q - 1) + 1
    public_key = pow(G, witness % Q, P)
    commitment = pow(G, nonce, P)
    challenge = hash_to_scalar(out, public_key, commitment)
    response = (nonce + challenge * (witness % Q)) % Q
    return Proof(
        out=out,
        public_key=public_key,
        commitment=commitment,
        response=response,
    )


def verify_proof(proof: Proof) -> bool:
    challenge = hash_to_scalar(proof.out, proof.public_key, proof.commitment)
    left = pow(G, proof.response, P)
    right = (proof.commitment * pow(proof.public_key, challenge, P)) % P
    return left == right


def main() -> None:
    out = 35
    witness = 3

    print("=== 公共语句 ===")
    print(f"方程: x^3 + x + 5 = {out}")
    print(f"公开参数: p={P}, q={Q}, g={G}")
    print()

    print("=== witness 检查 ===")
    solutions = find_integer_solutions(out)
    print(f"整数范围[-100, 100]内的解: {solutions}")
    print(f"Alice 持有的 witness x = {witness}")
    print(f"代入验证: {witness}^3 + {witness} + 5 = {equation(witness)}")
    print()

    print("=== 证明生成 ===")
    proof = generate_proof(out, witness)
    print(json.dumps(asdict(proof), indent=2, ensure_ascii=False))
    print()

    print("=== 证明验证 ===")
    ok = verify_proof(proof)
    print(f"验证结果: {ok}")
    print()

    print("=== 篡改测试 ===")
    bad_proof = Proof(
        out=proof.out,
        public_key=proof.public_key,
        commitment=proof.commitment,
        response=(proof.response + 1) % Q,
    )
    print(f"篡改后的验证结果: {verify_proof(bad_proof)}")


if __name__ == "__main__":
    main()
