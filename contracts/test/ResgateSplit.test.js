const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ResgateSplit", function () {
  async function deploy() {
    const [deployer, service, client, payer] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("ResgateSplit");
    const contract = await Factory.deploy(service.address, client.address);
    await contract.waitForDeployment();
    return { contract, deployer, service, client, payer };
  }

  it("splits a voluntary payment equally", async function () {
    const { contract, service, client, payer } = await deploy();
    const amount = ethers.parseEther("1");
    const caseId = ethers.keccak256(ethers.toUtf8Bytes("case-001"));

    const serviceBefore = await ethers.provider.getBalance(service.address);
    const clientBefore = await ethers.provider.getBalance(client.address);

    await expect(
      contract.connect(payer).payAndSplit(caseId, { value: amount })
    ).to.emit(contract, "SplitPaid");

    expect((await ethers.provider.getBalance(service.address)) - serviceBefore)
      .to.equal(amount / 2n);
    expect((await ethers.provider.getBalance(client.address)) - clientBefore)
      .to.equal(amount - amount / 2n);
  });

  it("rejects zero-value payments", async function () {
    const { contract, payer } = await deploy();
    const caseId = ethers.keccak256(ethers.toUtf8Bytes("case-002"));
    await expect(
      contract.connect(payer).payAndSplit(caseId, { value: 0 })
    ).to.be.revertedWithCustomError(contract, "ZeroPayment");
  });

  it("rejects an empty case reference", async function () {
    const { contract, payer } = await deploy();
    await expect(
      contract.connect(payer).payAndSplit(ethers.ZeroHash, {
        value: ethers.parseEther("0.1")
      })
    ).to.be.revertedWithCustomError(contract, "InvalidCaseId");
  });

  it("rejects identical recipients at deployment", async function () {
    const [same] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("ResgateSplit");
    await expect(
      Factory.deploy(same.address, same.address)
    ).to.be.revertedWithCustomError(Factory, "ZeroAddress");
  });
});
