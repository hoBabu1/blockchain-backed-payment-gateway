//SPDX-License-Identifier:MIT

pragma solidity 0.8.20;

import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract OnChainPaymentGateWay {
    using SafeERC20 for IERC20;

    IERC20 public immutable underlying;

    constructor(address _paymentToken) {
        underlying = IERC20(_paymentToken);
    }
}
