import { Component, Suspense, lazy, useState } from 'react';
import './ClinicalTwin.css';

const ClinicalTwin = lazy(() => import('./ClinicalTwin'));

function hasWebGL() {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

class TwinBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error('3D twin failed, showing 2D view', error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function Loading() {
  return (
    <div className="twin twin-loading">
      <div className="twin-loading-orb" />
      Building clinical digital twin
    </div>
  );
}

// 3D blast radius when WebGL is available; the 2D panels otherwise.
export default function ClinicalTwinPanel({ fallback, ...props }) {
  const [webgl] = useState(hasWebGL);
  if (!webgl || !props.facility || !props.graph) return props.facility && props.graph ? fallback : <Loading />;
  return (
    <TwinBoundary fallback={fallback}>
      <Suspense fallback={<Loading />}>
        <ClinicalTwin {...props} />
      </Suspense>
    </TwinBoundary>
  );
}
