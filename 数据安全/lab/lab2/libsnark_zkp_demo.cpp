#include <iostream>

#include <libff/algebra/curves/alt_bn128/alt_bn128_pp.hpp>
#include <libff/common/profiling.hpp>
#include <libsnark/gadgetlib1/protoboard.hpp>
#include <libsnark/reductions/r1cs_to_qap/r1cs_to_qap.hpp>
#include <libsnark/zk_proof_systems/ppzksnark/r1cs_gg_ppzksnark/r1cs_gg_ppzksnark.hpp>

using namespace libsnark;
using namespace libff;

int main() {
    typedef alt_bn128_pp ppT;
    typedef Fr<ppT> FieldT;

    ppT::init_public_params();
    start_profiling();

    protoboard<FieldT> pb;
    pb_variable<FieldT> out;
    pb_variable<FieldT> x;
    pb_variable<FieldT> x2;
    pb_variable<FieldT> x3;

    out.allocate(pb, "out");
    x.allocate(pb, "x");
    x2.allocate(pb, "x2");
    x3.allocate(pb, "x3");

    pb.set_input_sizes(1);

    pb.add_r1cs_constraint(
        r1cs_constraint<FieldT>(x, x, x2),
        "x^2"
    );
    pb.add_r1cs_constraint(
        r1cs_constraint<FieldT>(x2, x, x3),
        "x^3"
    );
    pb.add_r1cs_constraint(
        r1cs_constraint<FieldT>(x3 + x + FieldT("5"), FieldT::one(), out),
        "x^3 + x + 5 = out"
    );

    pb.val(out) = FieldT("35");
    pb.val(x) = FieldT("3");
    pb.val(x2) = FieldT("9");
    pb.val(x3) = FieldT("27");

    const auto constraint_system = pb.get_constraint_system();

    std::cout << "=== R1CS information ===" << std::endl;
    std::cout << "constraints: " << constraint_system.num_constraints() << std::endl;
    std::cout << "primary input size: " << pb.primary_input().size() << std::endl;
    std::cout << "auxiliary input size: " << pb.auxiliary_input().size() << std::endl;
    std::cout << std::endl;

    const auto keypair = r1cs_gg_ppzksnark_generator<ppT>(constraint_system);
    const auto proof = r1cs_gg_ppzksnark_prover<ppT>(
        keypair.pk,
        pb.primary_input(),
        pb.auxiliary_input()
    );

    const bool verified = r1cs_gg_ppzksnark_verifier_strong_IC<ppT>(
        keypair.vk,
        pb.primary_input(),
        proof
    );

    r1cs_primary_input<FieldT> wrong_input;
    wrong_input.emplace_back(FieldT("36"));
    const bool wrong_verified = r1cs_gg_ppzksnark_verifier_strong_IC<ppT>(
        keypair.vk,
        wrong_input,
        proof
    );

    std::cout << "=== Public statement ===" << std::endl;
    std::cout << "Prove knowledge of x such that x^3 + x + 5 = out" << std::endl;
    std::cout << "public out = 35" << std::endl;
    std::cout << std::endl;

    std::cout << "=== Witness assignment ===" << std::endl;
    std::cout << "x = 3, x2 = 9, x3 = 27" << std::endl;
    std::cout << std::endl;

    std::cout << "=== Verification ===" << std::endl;
    std::cout << "proof accepted: " << std::boolalpha << verified << std::endl;
    std::cout << "tampered public input accepted: " << std::boolalpha << wrong_verified << std::endl;

    return verified && !wrong_verified ? 0 : 1;
}
