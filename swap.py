import time
import alice
import bob

######################################################################
#                                                                    #
#                                                                    #
#              CS251 Project 2: Cross-chain Atomic Swap              #
#                                                                    #
#                                                                    #
#                                                                    #
#              Written by: Max Spero                                 #
#              October 22, 2018                                      #
#              Version 1.0.1                                         #
#              小组成员：2011428 王天行                                #
#                       2012679 王娇妹                                #
######################################################################
#
# In this assignment we will implement a cross-chain atomic swap
# between two parties, Alice and Bob.
#
# Alice has bitcoin on BTC Testnet3 (the standard bitcoin testnet).
# Bob has bitcoin on BCY Testnet (Blockcypher's Bitcoin testnet).
# They want to trade ownership of their respective coins securely,
# something that can't be done with a simple transaction because
# they are on different blockchains.
#
# This method also works between other cryptocurrencies and altcoins,
# for example trading n Bitcoin for m Litecoin.
# 
# The idea here is to set up transactions around a secret x, that
# only one party (Alice) knows. In these transactions only H(x) 
# will be published, leaving x secret. 
# 
# Transactions will be set up in such a way that once x is revealed,
# both parties can redeem the coins sent by the other party.
#
# If x is never revealed, both parties will be able to retrieve their
# original coins safely, without help from the other.
#
#
#
######################################################################
#                           BTC Testnet3                             #     
######################################################################
#
# Alice ----> UTXO ----> Bob (with x)
#               |
#               |
#               V
#             Alice (after 48 hours)
#
######################################################################
#                            BCY Testnet                             #
######################################################################
#
#   Bob ----> UTXO ----> Alice (with x)
#               |
#               |
#               V
#              Bob (after 24 hours)
#
######################################################################

######################################################################
#
# Configured for your addresses
# 
# TODO: Fill in all of these fields

# 0.001 每份0.0009
alice_txid_to_spend     = "19afad7e9a6d2f83b760b827666762a18e9b25c66e8d37098d37f03a478be85f" 
alice_utxo_index        = 2
alice_amount_to_send    = 0.0009
#
bob_txid_to_spend       = "0e978a39565bd40299bce70a67a5fac921dbccfc17fc6527794c438948f20f67"
bob_utxo_index          = 2
bob_amount_to_send      = 0.00008

# Get current block height (for locktime) in 'height' parameter for each blockchain (and put it into swap.py):
#  curl https://api.blockcypher.com/v1/btc/test3
btc_test3_chain_height  = 2408899

#  curl https://api.blockcypher.com/v1/bcy/test
bcy_test_chain_height   = 565982

# Parameter for how long Alice/Bob should have to wait before they can take back their coins
## alice_locktime MUST be > bob_locktime
alice_locktime = 5
bob_locktime = 3

tx_fee = 0.00001

broadcast_transactions = True
#alice_redeems = False
alice_redeems = True
#
#
######################################################################


######################################################################
#
# Read the following function.
# 
# There's nothing to implement here, but it outlines the structure
# of how Alice and Bob will communicate to perform this cross-
# chain atomic swap.
#
# You will run swap.py to test your code.
#
######################################################################

def atomic_swap(broadcast_transactions=False, alice_redeems=True):
    # Alice reveals the hash of her secret x but not the secret itself
    hash_of_secret = alice.hash_of_secret()

    # Alice creates a transaction redeemable by Bob (with x) or by Bob and Alice
    alice_swap_tx, alice_swap_scriptPubKey = alice.alice_swap_tx(
        alice_txid_to_spend,
        alice_utxo_index,
        alice_amount_to_send - tx_fee,
    )

    # Alice creates a time-locked transaction to return coins to herself
    alice_return_coins_tx = alice.return_coins_tx(
        alice_amount_to_send - (2 * tx_fee),
        alice_swap_tx,
        btc_test3_chain_height + alice_locktime,
        alice_swap_scriptPubKey,
    )

    # Alice asks Bob to sign her transaction
    bob_signature_BTC = bob.sign_BTC(alice_return_coins_tx, alice_swap_scriptPubKey)

    # Alice broadcasts her first transaction, only after Bob signs this one
    if broadcast_transactions:
        alice.broadcast_BTC(alice_swap_tx)

    # The same situation occurs, with roles reversed
    bob_swap_tx, bob_swap_scriptPubKey = bob.bob_swap_tx(
        bob_txid_to_spend,
        bob_utxo_index,
        bob_amount_to_send - tx_fee,
        hash_of_secret,
    )
    bob_return_coins_tx = bob.return_coins_tx(
        bob_amount_to_send - (2 * tx_fee),
        bob_swap_tx,
        bcy_test_chain_height + bob_locktime,
    )

    alice_signature_BCY = alice.sign_BCY(bob_return_coins_tx, bob_swap_scriptPubKey)

    if broadcast_transactions:
        bob.broadcast_BCY(bob_swap_tx)

    if broadcast_transactions:
        print('Sleeping for 20 minutes to let transactions confirm...')
        time.sleep(60 * 20)

    if alice_redeems:
        # Alice redeems her coins, revealing x publicly (it's now on the blockchain)
        alice_redeem_tx, alice_secret_x = alice.redeem_swap(
            bob_amount_to_send - (2 * tx_fee),
            bob_swap_tx,
            bob_swap_scriptPubKey,
        )
        if broadcast_transactions:
            alice.broadcast_BCY(alice_redeem_tx)

        # Once x is revealed, Bob may also redeem his coins
        bob_redeem_tx = bob.redeem_swap(
            alice_amount_to_send - (2 * tx_fee),
            alice_swap_tx,
            alice_swap_scriptPubKey,
            alice_secret_x,
        )
        if broadcast_transactions:
            bob.broadcast_BTC(bob_redeem_tx)
    else:
        
        # Bob and Alice may take back their original coins after the specified time has passed
        completed_bob_return_tx = bob.complete_return_tx(
            bob_return_coins_tx,
            bob_swap_scriptPubKey,
            alice_signature_BCY,
        )
        completed_alice_return_tx = alice.complete_return_tx(
            alice_return_coins_tx,
            alice_swap_scriptPubKey,
            bob_signature_BTC,
        )
        if broadcast_transactions:
            print('Sleeping for bob_locktime blocks to pass locktime...')
            time.sleep(10 * 60 * bob_locktime)
            bob.broadcast_BCY(completed_bob_return_tx)

            print('Sleeping for alice_locktime blocks to pass locktime...')
            time.sleep(10 * 60 * max(alice_locktime - bob_locktime, 0))
            alice.broadcast_BTC(completed_alice_return_tx)

if __name__ == '__main__':
    atomic_swap(broadcast_transactions, alice_redeems)
##########################################################################
#
#                       alice_redeems = False
#                       output：
###########################################################################
'''

Alice swap tx (BTC) created successfully!
201 Created
{
  "tx": {
    "block_height": -1,
    "block_index": -1,
    "hash": "3d30fc4117bd390174350c42e0e353a99e1d070052fdc8efacba5fcbe4ee8ec4",
    "addresses": [
      "n4ctyMcqGV3EsfGrmJwyoeiMZqqVCaGqEj"
    ],
    "total": 89000,
    "fees": 11000,
    "size": 302,
    "vsize": 302,
    "preference": "low",
    "relayed_by": "60.29.153.38",
    "received": "2022-12-02T14:17:28.542040953Z",
    "ver": 1,
    "double_spend": false,
    "vin_sz": 1,
    "vout_sz": 1,
    "confirmations": 0,
    "inputs": [
      {
        "prev_hash": "19afad7e9a6d2f83b760b827666762a18e9b25c66e8d37098d37f03a478be85f",
        "output_index": 2,
        "script": "483045022100b2f0bbc9ab6af34927a299028c06c46f41565a6f08a9d71d2d360e9db8b041d2022028148a9fbee4f0d3380ee8f2d2b8904b9da5142246281452c3da2040e618718f0121028c95860ccf90ebf808fa09d5c0bd345d454c8d7a88474878d38bc8e194e8da15",
        "output_value": 100000,
        "sequence": 4294967295,
        "addresses": [
          "n4ctyMcqGV3EsfGrmJwyoeiMZqqVCaGqEj"
        ],
        "script_type": "pay-to-pubkey-hash",
        "age": 2408900
      }
    ],
    "outputs": [
      {
        "value": 89000,
        "script": "74528763a914853b775079232503df966e626618e1d388a9572088210232d10d2b82b0cff285037945d2ecca91ea4d8d315b4fb2d35f13c23708f398d8ac675221028c95860ccf90ebf808fa09d5c0bd345d454c8d7a88474878d38bc8e194e8da15210232d10d2b82b0cff285037945d2ecca91ea4d8d315b4fb2d35f13c23708f398d852ae68",
        "addresses": null,
        "script_type": "unknown"
      }
    ]
  }
}
Bob swap tx (BCY) created successfully!
201 Created
{
  "tx": {
    "block_height": -1,
    "block_index": -1,
    "hash": "e7d953db5412716c87eddb81d39982148727d35ba714f5aa5e6a7b8bf975e019",
    "addresses": [
      "BywqtdXvDivdjMUBaYF3JD8T92ifaJUpqf"
    ],
    "total": 7000,
    "fees": 2000,
    "size": 302,
    "vsize": 302,
    "preference": "low",
    "relayed_by": "60.29.153.38",
    "received": "2022-12-02T14:17:30.414265396Z",
    "ver": 1,
    "double_spend": false,
    "vin_sz": 1,
    "vout_sz": 1,
    "confirmations": 0,
    "inputs": [
      {
        "prev_hash": "0e978a39565bd40299bce70a67a5fac921dbccfc17fc6527794c438948f20f67",
        "output_index": 2,
        "script": "483045022100ec1f28af6d05342b84e30aa3ff07d7e37c2479d188991a117bd6d530e93ebf270220408c146e5c0c256f525e904051bd5c9835d19eb5fc1f048d5971207d7915927b012102aa31bf6e675f70dbf669ea1545f5b0aa91fcf089189e01854799b7baca3585b5",
        "output_value": 9000,
        "sequence": 4294967295,
        "addresses": [
          "BywqtdXvDivdjMUBaYF3JD8T92ifaJUpqf"
        ],
        "script_type": "pay-to-pubkey-hash",
        "age": 565975
      }
    ],
    "outputs": [
      {
        "value": 7000,
        "script": "74528763a914853b775079232503df966e626618e1d388a95720882102521ff54ff64fc5689b9636dd9ce25db4bf34d91e5847708dff00e0aa32a1af3cac67522102aa31bf6e675f70dbf669ea1545f5b0aa91fcf089189e01854799b7baca3585b52102521ff54ff64fc5689b9636dd9ce25db4bf34d91e5847708dff00e0aa32a1af3c52ae68",
        "addresses": null,
        "script_type": "unknown"
      }
    ]
  }
}
Sleeping for 20 minutes to let transactions confirm...
Bob return coins (BCY) tx created successfully!
Alice return coins tx (BTC) created successfully!
'''
##########################################################################
##########################################################################
#
#                       alice_redeems = True
#                       output：
###########################################################################
'''
wjm@LAPTOP-EVN3O6SP:~/mypros/Exercise4$ python3 swap.py
Alice swap tx (BTC) created successfully!
201 Created
{
  "tx": {
    "block_height": -1,
    "block_index": -1,
    "hash": "5ff566a89cf4fefd6287d7ccbceba0bdead77f932be197242b31b9af331366c2",
    "addresses": [
      "n4ctyMcqGV3EsfGrmJwyoeiMZqqVCaGqEj"
    ],
    "total": 89000,
    "fees": 11000,
    "size": 302,
    "vsize": 302,
    "preference": "low",
    "relayed_by": "202.113.19.218",
    "received": "2022-12-02T15:45:06.803035129Z",
    "ver": 1,
    "double_spend": false,
    "vin_sz": 1,
    "vout_sz": 1,
    "confirmations": 0,
    "inputs": [
      {
        "prev_hash": "19afad7e9a6d2f83b760b827666762a18e9b25c66e8d37098d37f03a478be85f",
        "output_index": 3,
        "script": "483045022100c6bf3deac01b34fddff02635beccc0298343da76409c529904bd92101897c5490220366e3f25bbd0bc38f778e03014a52fc412ae15589c08484abf026f7c71f474240121028c95860ccf90ebf808fa09d5c0bd345d454c8d7a88474878d38bc8e194e8da15",
        "output_value": 100000,
        "sequence": 4294967295,
        "addresses": [
          "n4ctyMcqGV3EsfGrmJwyoeiMZqqVCaGqEj"
        ],
        "script_type": "pay-to-pubkey-hash",
        "age": 2408900
      }
    ],
    "outputs": [
      {
        "value": 89000,
        "script": "74528763a914853b775079232503df966e626618e1d388a9572088210232d10d2b82b0cff285037945d2ecca91ea4d8d315b4fb2d35f13c23708f398d8ac675221028c95860ccf90ebf808fa09d5c0bd345d454c8d7a88474878d38bc8e194e8da15210232d10d2b82b0cff285037945d2ecca91ea4d8d315b4fb2d35f13c23708f398d852ae68",
        "addresses": null,
        "script_type": "unknown"
      }
    ]
  }
}
Bob swap tx (BCY) created successfully!
201 Created
{
  "tx": {
    "block_height": -1,
    "block_index": -1,
    "hash": "e0375500eb0daa09fc1eaaa738f1d3b2ffc6a3db0edf4f95b7ed17bd1ed9091b",
    "addresses": [
      "BywqtdXvDivdjMUBaYF3JD8T92ifaJUpqf"
    ],
    "total": 7000,
    "fees": 2000,
    "size": 301,
    "vsize": 301,
    "preference": "low",
    "relayed_by": "202.113.19.218",
    "received": "2022-12-02T15:45:08.277148955Z",
    "ver": 1,
    "double_spend": false,
    "vin_sz": 1,
    "vout_sz": 1,
    "confirmations": 0,
    "inputs": [
      {
        "prev_hash": "0e978a39565bd40299bce70a67a5fac921dbccfc17fc6527794c438948f20f67",
        "output_index": 3,
        "script": "47304402203a50e9181d90aadba16b22f9359ccd5d2b0fb518c5ec5f67263357306eb470d302206de76927eeb6f0cd5e6be99c48cc310ea464af9a3cb51d3b4a0fdfc28c4bca4b012102aa31bf6e675f70dbf669ea1545f5b0aa91fcf089189e01854799b7baca3585b5",
        "output_value": 9000,
        "sequence": 4294967295,
        "addresses": [
          "BywqtdXvDivdjMUBaYF3JD8T92ifaJUpqf"
        ],
        "script_type": "pay-to-pubkey-hash",
        "age": 565975
      }
    ],
    "outputs": [
      {
        "value": 7000,
        "script": "74528763a914853b775079232503df966e626618e1d388a95720882102521ff54ff64fc5689b9636dd9ce25db4bf34d91e5847708dff00e0aa32a1af3cac67522102aa31bf6e675f70dbf669ea1545f5b0aa91fcf089189e01854799b7baca3585b52102521ff54ff64fc5689b9636dd9ce25db4bf34d91e5847708dff00e0aa32a1af3c52ae68",
        "addresses": null,
        "script_type": "unknown"
      }
    ]
  }
}
Sleeping for 20 minutes to let transactions confirm...
Alice redeem from swap tx (BCY) created successfully!
'''