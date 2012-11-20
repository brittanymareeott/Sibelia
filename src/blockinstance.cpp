//***************************************************************************
//* Copyright (c) 2012 Saint-Petersburg Academic University
//* All Rights Reserved
//* See file LICENSE for details.
//****************************************************************************

#include "blockinstance.h"

namespace SyntenyFinder
{
	typedef boost::function<size_t(const BlockInstance&)> SizeF;
	SizeF getId = boost::bind(&BlockInstance::GetBlockId, _1);
	SizeF getChr = boost::bind(&BlockInstance::GetChr, _1);
	SizeF getStart = boost::bind(&BlockInstance::GetStart, _1);
	const BlockComparer compareById = boost::bind(CompareBlocks<SizeF>, _1, _2, getId);
	const BlockComparer compareByChr = boost::bind(CompareBlocks<SizeF>, _1, _2, getChr);
	const BlockComparer compareByStart = boost::bind(CompareBlocks<SizeF>, _1, _2, getStart);
}