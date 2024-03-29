from topSupport.tools.logger import getLogger
log = getLogger()


import ROOT, os, numpy
import cPickle as pickle
from topSupport.tools.helpers import copyIndexPHP, copyGitInfo, addHist
from topSupport.plots.plot import Plot
from topSupport.samples.Sample import getSampleFromStack
from topSupport.tools.lock import lock

ROOT.TH1.SetDefaultSumw2()
ROOT.TH2.SetDefaultSumw2()


def equalBinning():
  def equalizeBins(hists):
    nx = hists.values()[0].GetXaxis().GetNbins()
    ny = hists.values()[0].GetYaxis().GetNbins()
    template = ROOT.TH2D('template', 'template', nx, numpy.array(range(nx+1)).astype(float), ny, numpy.array(range(ny+1)).astype(float))
    for key in hists.keys():
      newHist = template.Clone(hists[key].GetName())
      for i in range(nx+1):
        for j in range(ny+1):
          newHist.SetBinContent(i,j, hists[key].GetBinContent(i, j))
          newHist.SetBinError(i,j, hists[key].GetBinError(i, j))
      for i in range(1, nx+1):
        newHist.GetXaxis().SetBinLabel(i, str(int(hists[key].GetXaxis().GetBinLowEdge(i))) + '-' + str(int(hists[key].GetXaxis().GetBinUpEdge(i))) )
      for i in range(1, ny+1):
        newHist.GetYaxis().SetBinLabel(i, str(int(hists[key].GetYaxis().GetBinLowEdge(i))) + '-' + str(int(hists[key].GetYaxis().GetBinUpEdge(i))) )
      hists[key]=newHist
  return [equalizeBins]


# def xAxisLabels2D(labels):
#   def xapplyLabels(hists):
#     for i, l in enumerate(labels):
#       for h in hists:
#         h.GetXaxis().SetBinLabel(i+1, l)
#   return [xapplyLabels]

# def yAxisLabels2D(labels):
#   def yapplyLabels(hists):
#     for h in hists:
#       for i, l in enumerate(labels):
#         h.GetYaxis().SetBinLabel(i+1, l)
#   return [yapplyLabels]

def normalizeAlong(axis):
  # normalize every column
  if axis == 'y':
    def normAlongY(hists):
      hists = hists.values()
      sumH = hists[0].Clone()
      for h in hists[1:]:
        sumH.Add(h)
      proj = sumH.ProjectionX("projx", 1)
      for h in hists:
        for i in range(1, h.GetXaxis().GetNbins()+1):
          for j in range(1, h.GetYaxis().GetNbins()+1):
            if proj.GetBinContent(i) == 0 and h.GetBinContent(i, j) == 0: continue
            h.SetBinContent(i, j, h.GetBinContent(i, j)/proj.GetBinContent(i))
    return [normAlongY]
  # normalize every row
  elif axis == 'x':
    def normAlongX(hists):
      hists = hists.values()
      sumH = hists[0].Clone()
      for h in hists[1:]:
        sumH.Add(h)
      proj = sumH.ProjectionY("projy", 1)
      for h in hists:
        for i in range(1, h.GetXaxis().GetNbins()+1):
          for j in range(1, h.GetYaxis().GetNbins()+1):
            if proj.GetBinContent(j) == 0 and h.GetBinContent(i, j) == 0: continue
            h.SetBinContent(i, j, h.GetBinContent(i, j)/proj.GetBinContent(j))
    return [normAlongX]  
  else:
    log.debug('invalid axis to normlize along')
    return[]

def xAxisLabels2D(labels):
  def applyLabels(hists):
    hists = hists.values()
    for h in hists:
      for i, l in enumerate(labels):
        h.GetXaxis().SetBinLabel(i+1, l)
  return [applyLabels]

def yAxisLabels2D(labels):
  def applyLabels(hists):
    hists = hists.values()
    for h in hists:
      for i, l in enumerate(labels):
        h.GetYaxis().SetBinLabel(i+1, l)
  return [applyLabels]

  
#
# Plot class for 2D
# Disable warnings about different number of arguments for overriden method 
# pylint: disable=W0221
#
class Plot2D(Plot):
  defaultStack = None

  @staticmethod
  def setDefaults(stack = None):
    Plot2D.defaultStack = stack

  def __init__(self, name, texX, varX, binningX, texY, varY, binningY, stack=None, histModifications=[]):  # pylint: disable=R0913
    Plot.__init__(self, name, texX, varX, binningX, stack=(stack if stack else Plot2D.defaultStack), texY=texY, overflowBin=False, normBinWidth=False)
    self.varY        = varY
    self.binningX    = self.binning
    self.histModifications = histModifications

    if type(binningY)==type([]):   self.binningY = (len(binningY)-1, numpy.array(binningY))
    elif type(binningY)==type(()): self.binningY = binningY

    self.histos = {}
    for s in sum(self.stack, []):
      name           = self.name + s.name
      self.histos[s] = ROOT.TH2D(name, name, *(self.binningX+self.binningY))


  def fill(self, sample, weight=1.):
    self.histos[sample].Fill(self.varX(sample.chain), self.varY(sample.chain), weight)


  #
  # Stacking the hist, called during the draw function
  #
  def stackHists(self, histsToStack, sorting=True):
    if sorting: histsToStack.sort(key=lambda h  : -h.Integral())

    # Add up stacks
    for i, _ in enumerate(histsToStack):
      for j in range(i+1, len(histsToStack)):
        histsToStack[i].Add(histsToStack[j])

    return histsToStack[:1] # do not show sub-contributions in 2D

  def getYields(self, binX=None, binY=None):
    if binX and binY: return {s.name : h.GetBinContent(binX, binY) for s, h in self.histos.iteritems()}
    else:             return {s.name : h.Integral()                for s, h in self.histos.iteritems()}

  def saveToCache(self, dir, sys):
    try:    os.makedirs(os.path.join(dir))
    except: pass

    resultFile = os.path.join(dir, self.name + '.pkl')
    histos     = {s.nameNoSys+s.texName: h for s, h in self.histos.iteritems()}
    plotName   = self.name+(sys if sys else '')
    try:
      with lock(resultFile, 'rb', keepLock=True) as f: allPlots = pickle.load(f)
      allPlots.update({plotName : histos})
    except:
      allPlots = {plotName : histos}
    with lock(resultFile, 'wb', existingLock=True) as f: pickle.dump(allPlots, f)
    log.info("Plot " + plotName + " saved to cache")

  def applyMods(self):
    # different from 1D plots, hand all hists to modification function
    for modification in self.histModifications: 
      if type(modification) == list: 
        modification[0](self.histos)
      else: 
        modification(self.histos)

  #
  # Draw function, might need some refactoring
  # pylint: disable=R0913,R0914,R0915
  #
  def draw(self, \
          zRange = None,
          extensions = None, 
          plot_directory = ".", 
          logX = False, logY = False, logZ = True, 
          drawObjects = None,
          drawOption = 'COLZ',
          widths = None,
          histModifications = [],
          ):
    ''' plot: a Plot2D instance
        zRange: None ( = ROOT default) or [low, high] 
        extensions: ["pdf", "png", "root"] (default)
        logX: True/False (default), logY: True/False(default), logZ: True/False(default)
        drawObjects = [] Additional ROOT objects that are called by .Draw() 
        widths = {} (default) to update the widths. Values are {'y_width':500, 'x_width':500, 'y_ratio_width':200}
    '''
    clean = False
    if drawOption.count('clean'):
      drawOption = drawOption.replace('clean', '')
      clean = True


    import topSupport.tools.style as style
    style.setDefault2D(drawOption.count('COLZ'))

    # default_widths    
    default_widths = {'y_width':800, 'x_width':800, 'y_ratio_width':200}
    if widths: default_widths.update(widths)

    histDict = {i: h.Clone() for i, h in self.histos.iteritems()}

    # Apply style to histograms and add overflow bin
    for s, h in histDict.iteritems():
      if hasattr(s, 'style2D'): s.style2D(h)
      h.texName = s.texName

    # Transform histDict --> histos where the stacks are added up
    # Note self.stack is of form [[A1, A2, A3,...],[B1,B2,...],...] where the sublists need to be stacked
    histos = []
    for stack in self.stack:
      histsToStack = [histDict[s] for s in stack]
      histos.append(self.stackHists(histsToStack))

    # delete canvas if it exists
    if hasattr("ROOT","c1"): del ROOT.c1 
    c1 = ROOT.TCanvas("ROOT.c1", "drawHistos", 200, 10, default_widths['x_width'], default_widths['y_width'])
    c1.SetLogx(logX)
    c1.SetLogy(logY)
    c1.SetLogz(logZ)

    same = ""
    for histo in (sum(histos, []) if drawOption.count('SCAT') else histos[0]):
      histo.SetTitle('')
      histo.GetXaxis().SetTitle(self.texX)
      histo.GetYaxis().SetTitle(self.texY)
      if zRange is not None:
        histo.GetZaxis().SetRangeUser( *zRange )
      if clean:
        histo.GetZaxis().SetRangeUser(histo.GetMaximum()*0.0004, histo.GetMaximum()*1.03)
      style.commonStyle(histo)
      # hacky overrite of commonStyle
      histo.GetXaxis().SetTitleOffset(1.4)
      histo.GetZaxis().SetLabelSize(0.035)
      histo.Draw(drawOption+same)
      same = "same"

    c1.RedrawAxis()

    if drawObjects:
      for o in drawObjects:
        try:    o.Draw()
        except: log.debug( "drawObjects has something I can't Draw(): %r", o)

    try:    os.makedirs(plot_directory)
    except: pass
    copyIndexPHP(plot_directory)

    copyGitInfo(os.path.join(plot_directory, self.name + '.gitInfo'))
    log.info('Creating output files for ' + self.name)
    for extension in (extensions if extensions else ["pdf", "png", "root","C"]):
      ofile = os.path.join( plot_directory, "%s.%s"%(self.name, extension) )
      c1.Print( ofile )
    del c1

def add2DPlots(plotA, plotB):
  # log.info('Adding two plots, attributes taken from A, plot B has the following differences:')
  # log.info(set(tuple(plotA.__dict__.items())) - set(tuple(plotA.__dict__.items())))
  for sample, hist in plotA.histos.iteritems():
    try:
      hist = addHist(hist, plotB.histos[getSampleFromStack(plotB.stack, sample.name)])
    except: log.warning('mismatch between histograms/samples in the plots')
  return plotA
