# Post-Quantum Cryptography: NIST Standards and Module-Lattice Algorithms

## Abstract
Shor's quantum algorithm factors large integers in polynomial time $O((\log N)^3)$, rendering current RSA and Elliptic Curve Cryptography (ECC) protocols vulnerable to cryptanalytic exposure by fault-tolerant quantum computers. This document covers the newly ratified NIST post-quantum standards.

## 1. Primary NIST Standards: ML-KEM (Kyber) and ML-DSA (Dilithium)
In 2024, the National Institute of Standards and Technology (NIST) published Federal Information Processing Standards (FIPS):
- **FIPS 203 (ML-KEM, formerly CRYSTALS-Kyber)**: Primary standard for general public-key encryption and Key Encapsulation Mechanisms. It is grounded in the hardness of the Module Learning With Errors (M-LWE) lattice problem over polynomial rings.
- **FIPS 204 (ML-DSA, formerly CRYSTALS-Dilithium)**: Primary standard for digital signatures, based on the Module Short Integer Solution (M-SIS) problem.
- **FIPS 205 (SLH-DSA, formerly SPHINCS+)**: Stateless hash-based digital signature standard providing fallback security independent of lattice assumptions.

## 2. Parameter Sets and Performance Benchmarks
ML-KEM-768 provides security equivalent to AES-192, featuring public key sizes of 1,184 bytes and ciphertext sizes of 1,088 bytes. Key generation, encapsulation, and decapsulation execute in under 15 microseconds on modern x86-64 CPUs with AVX2 vector extensions—substantially faster than classic 3072-bit RSA.

## 3. Hybrid Post-Quantum Key Exchange in TLS 1.3
Major Internet infrastructure adopts hybrid key exchange mechanisms combining classic X25519 elliptic curve Diffie-Hellman with ML-KEM-768 (X25519Kyber768Draft00). This protects current encrypted sessions against retroactive "Harvest Now, Decrypt Later" quantum adversary attacks while maintaining backward security guarantees.
