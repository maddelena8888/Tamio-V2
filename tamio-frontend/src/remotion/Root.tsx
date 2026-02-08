import { Composition } from 'remotion';
import { TamioDemo } from './TamioDemo';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="TamioDemo"
        component={TamioDemo}
        durationInFrames={1380} // 46 seconds at 30fps
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="TamioDemoSquare"
        component={TamioDemo}
        durationInFrames={1380}
        fps={30}
        width={1080}
        height={1080}
      />
    </>
  );
};
