//SPDX-License-identifier:MIT

pragma solidity 0.8.20;

import {Script, console} from "../lib/forge-std/src/Script.sol";
import {MockUsdt} from "../src/MockUsdt.sol";
import {OnChainPaymentGateWay} from "../src/OnChainPaymentGateWay.sol";

import {IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract DeployOcpg is Script {
    OnChainPaymentGateWay ocpg;
    MockUsdt mUsdt;
    address owner = 0x096DD3EBFab85c85309477DDf3A18FC31ecBa33a;

    function run() external {
        vm.startBroadcast();
        mUsdt = new MockUsdt("Mock USDT", "mUSDT");
        ocpg = new OnChainPaymentGateWay(owner);

        ocpg.enableToken(IERC20(mUsdt));
        vm.stopBroadcast();

        console.log("Mock Token ", address(mUsdt));
        console.log("address of OnChainPaymentGateWay ", address(ocpg));
    }
}
