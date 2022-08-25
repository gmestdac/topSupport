from topSupport.tools.logger  import getLogger
from topSupport.tools.helpers import deltaR
from math import sqrt, atan, pi, tan
from math import log as logar
import ROOT
import os

log = getLogger()

#
# All functions to select objects, as well as some functions which add new variables based on the selected objects to the tree
#

#
# Helper functions
#
def getLorentzVector(pt, eta, phi, e):
  vector = ROOT.TLorentzVector()
  vector.SetPtEtaPhiE(pt, eta, phi, e)
  return vector

#
# Individual lepton selector
#
def leptonPt(tree, index):
  if tree._lFlavor[index]: return getattr(tree, '_lPt'+tree.muvar)[index]
  else:                    return getattr(tree, '_lPt'+tree.egvar)[index]

def leptonE(tree, index):
  if tree._lFlavor[index]: return getattr(tree, '_lE'+tree.muvar)[index]
  else:                    return getattr(tree, '_lE'+tree.egvar)[index]






# - Preselectie (zelfde als preUL)
# - Medium WP van de UL versie. Ik heb ook is met loose geprobeerd, maar da was ni overtuigend. => leptonMVAUL > 0.64


def looseMuonSelector(tree, index):
  if leptonPt(tree, index) < 10.:                       return False   
  if abs(tree._lEta[index]) > 2.4:                      return False   
  if not tree._miniIso[index] < 0.4:                    return False   
  if not abs(tree._3dIPSig[index]) < 8:                 return False   
  if not abs(tree._dxy[index]) < 0.05:                  return False   
  if not abs(tree._dz[index]) < 0.1:                    return False   
  if not tree._lPOGMedium[index]:                       return False   
  return True

def muonSelector(tree, index):
  if not looseMuonSelector(tree, index):                 return False
  # medium working point
  return tree._leptonMvaTOPUL[index] > 0.64



# Electronen: 
# - gewone preselectie van de elektronen, blijft hetzelfde als preUL
# - ecal gap veto: if ( abs(electronPtr->etaSuperCluster()) > 1.4442 && abs(electronPtr->etaSuperCluster()) < 1.566) return false;
# - Tight WP: leptonMVAUL > 0.81
# - charge consistency
# - conversion veto


def looseElectronSelector(tree, index):
  if leptonPt(tree, index) < 10. :                      return False   
  if abs(tree._lEta[index]) > 2.5:                      return False   
  if not tree._miniIso[index] < 0.4:                    return False   
  if not tree._lElectronMissingHits[index] < 2:         return False   
  if not abs(tree._3dIPSig[index]) < 8:                 return False   
  if not abs(tree._dxy[index]) < 0.05:                  return False   
  if not abs(tree._dz[index]) < 0.1:                    return False   
  return True

def electronSelector(tree, index):
  if not looseElectronSelector(tree, index):                 return False

  # cleaning
  for i in xrange(tree._nMu): # cleaning electrons around muons
    if not (tree._lFlavor[i] == 1 and looseMuonSelector(tree, i)): continue
    if deltaR(tree._lEta[i], tree._lEta[index], tree._lPhi[i], tree._lPhi[index]) < 0.05: return False
    
  # ecal gap veto 
  if 1.4442 < abs(tree._lEtaSC[index]) < 1.566:         return False

  # tight working point of V1 UL mva 0.81   and charge consistency and conversion veto
  return (tree._leptonMvaTOPUL[index] > 0.81 and tree._lElectronChargeConst[index] and tree._lElectronPassConvVeto[index] )





def leptonSelector(tree, index):
  if leptonPt(tree, index) < 10:       return False
  if tree._lFlavor[index] == 0:      
    return electronSelector(tree, index)
  elif tree._lFlavor[index] == 1:      
    return muonSelector(tree, index)
  else:                                return False


#
# Selects leptons passing the id and iso criteria, sorts them, and save their indices
#
def getSortKey(item): return item[0]

def select2l(t, n):
  ptAndIndex        = [(leptonPt(t, i), i) for i in t.leptons]
  if len(ptAndIndex) < 2: return False

  ptAndIndex.sort(reverse=True, key=getSortKey)
  n.l1              = ptAndIndex[0][1]
  n.l2              = ptAndIndex[1][1]
  n.l1_pt           = ptAndIndex[0][0]
  n.l2_pt           = ptAndIndex[1][0]
  n.isEE            = (t._lFlavor[n.l1]==0 and t._lFlavor[n.l2]==0)
  n.isEMu           = (t._lFlavor[n.l1]==0 and t._lFlavor[n.l2]==1) or (t._lFlavor[n.l1]==1 and t._lFlavor[n.l2]==0)
  n.isMuMu          = (t._lFlavor[n.l1]==1 and t._lFlavor[n.l2]==1)
  n.isOS            = t._lCharge[n.l1] != t._lCharge[n.l2]
  # return (leptonPt(t, n.l1) > 20 and n.isEE)
  n.nLepSel = len(ptAndIndex)

  return leptonPt(t, n.l1) > 20




def selectLeptons(t, n, minLeptons):
  t.leptons = [i for i in xrange(t._nLight) if leptonSelector(t, i)]
  if   minLeptons == 2: return select2l(t, n)
  else: return False #we're sticking to  2 leptons right now
  # elif minLeptons == 1: return select1l(t, n)
  # elif minLeptons == 0: return True


#
# Add invariant masses to the tree
#
def makeInvariantMasses(t, n):
  first  = getLorentzVector(leptonPt(t, n.l1), t._lEta[n.l1], t._lPhi[n.l1], leptonE(t, n.l1))   if len(t.leptons) > 0 else None
  second = getLorentzVector(leptonPt(t, n.l2), t._lEta[n.l2], t._lPhi[n.l2], leptonE(t, n.l2))   if len(t.leptons) > 1 else None
  n.mll  = (first+second).M()        if first and second else -1


def getEta(pt, pz):
  theta = atan(pt/pz)
  if( theta < 0 ): theta += pi
  return -logar(tan(theta/2))
